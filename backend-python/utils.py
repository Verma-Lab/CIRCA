import os
import json
import time
import logging
import concurrent.futures
from typing import List, Dict
import requests
from tqdm import tqdm
import pickle
import re
import pandas as pd

# Import your universal_extractor
from test import universal_extractor

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("corpus_builder.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Constants
PERPLEXITY_API_URL = "https://api.perplexity.ai/chat/completions"
PERPLEXITY_API_KEY = "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"  # REPLACE WITH VALID KEY
GOOGLE_API_KEY = "AIzaSyAq-ZOzYNYGjtZB1SlJVSDXMVd-CQldubE"  # REPLACE WITH VALID KEY
GEMINI_API_URL = "https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent"
OUTPUT_DIR = "./medical_corpus"
CORPUS_CACHE_FILE = "./corpus_cache.pkl"
MAX_ARTICLES_PER_SOURCE = 5
RETRY_DELAY = 2
MAX_RETRIES = 3

class MedicalCorpusBuilder:
    def __init__(self):
        """Initialize the Medical Corpus Builder."""
        os.makedirs(OUTPUT_DIR, exist_ok=True)
        self.cache = self._load_cache()
    
    def _load_cache(self) -> Dict:
        """Load cache from disk if available."""
        if os.path.exists(CORPUS_CACHE_FILE):
            try:
                with open(CORPUS_CACHE_FILE, 'rb') as f:
                    return pickle.load(f)
            except Exception as e:
                logger.warning(f"Could not load cache: {e}")
        return {"queries": {}, "extracted_articles": {}, "processed_corpus": {}}
    
    def _save_cache(self):
        """Save cache to disk."""
        try:
            with open(CORPUS_CACHE_FILE, 'wb') as f:
                pickle.dump(self.cache, f)
        except Exception as e:
            logger.warning(f"Could not save cache: {e}")
    
    def search_perplexity(self, disease_name: str, icd_code: str) -> List[Dict]:
        """Use Perplexity API to fetch web article links for the given ICD code."""
        cache_key = f"perplexity_{disease_name}_{icd_code}"
        # Comment out cache for debugging
        # if cache_key in self.cache["queries"]:
        #     logger.info(f"Using cached Perplexity query results for {cache_key}")
        #     return self.cache["queries"][cache_key]
        
        
        headers = {
            "Authorization": f"Bearer {PERPLEXITY_API_KEY}",
            "Content-Type": "application/json"
        }
        
        query = f"Provide a list of the top {MAX_ARTICLES_PER_SOURCE} reputable web articles or data sources related to {disease_name} (ICD-10 code: {icd_code}). Return the results in JSON format with each entry containing 'title' and 'url'. Focus on medical sources like journals, health websites, or research articles."
        
        payload = {
            "model": "sonar",
            "messages": [
                {"role": "system", "content": "You are a medical research assistant tasked with finding relevant web articles."},
                {"role": "user", "content": query}
            ],
            "max_tokens": 4096,
            "temperature": 0.2
        }
        
        articles = []
        for attempt in range(MAX_RETRIES):
            try:
                response = requests.post(PERPLEXITY_API_URL, headers=headers, json=payload, timeout=10)
                response.raise_for_status()
                data = response.json()
                
                content = data.get("choices", [{}])[0].get("message", {}).get("content", "")
                logger.debug(f"Perplexity response: {content[:500]}...")
                
                # Extract JSON from response
                json_match = re.search(r'```json\s*([\s\S]*?)\s*```|{\s*"[^"]+"\s*:\s*\[[\s\S]*?\]\s*}', content)
                if json_match:
                    json_str = json_match.group(1) or json_match.group(0)
                    result_data = json.loads(json_str.strip())
                    items = result_data if isinstance(result_data, list) else result_data.get("results", []) or result_data.get("articles", [])
                    
                    for item in items:
                        if isinstance(item, dict) and "url" in item:
                            articles.append({
                                "url": item["url"],
                                "title": item.get("title", "Unknown"),
                                "source": "perplexity"
                            })
                else:
                    # Fallback: extract URLs if no JSON
                    urls = re.findall(r'https?://[^\s)\'"]+', content)
                    articles = [{"url": url, "title": "Unknown", "source": "perplexity"} for url in urls]
                
                logger.info(f"Perplexity search successful: found {len(articles)} articles")
                break
            
            except Exception as e:
                logger.warning(f"Perplexity search attempt {attempt+1} failed: {e}")
                if 'response' in locals():
                    logger.debug(f"Response content: {response.text[:500]}...")
                if attempt < MAX_RETRIES - 1:
                    time.sleep(RETRY_DELAY)
                else:
                    logger.error(f"Failed to search Perplexity after {MAX_RETRIES} attempts")
        
        # Deduplicate and limit
        unique_articles = []
        seen_urls = set()
        for article in articles[:MAX_ARTICLES_PER_SOURCE]:
            if article["url"] not in seen_urls:
                seen_urls.add(article["url"])
                unique_articles.append(article)
        
        self.cache["queries"][cache_key] = unique_articles
        self._save_cache()
        return unique_articles
    
    def extract_article_data(self, article: Dict) -> Dict:
        """Extract article data using the universal_extractor."""
        url = article["url"]
        cache_key = url
        
        if cache_key in self.cache["extracted_articles"]:
            logger.info(f"Using cached article data for {cache_key}")
            return self.cache["extracted_articles"][cache_key]
        
        logger.info(f"Extracting data from {url}")
        try:
            # Pass to your universal_extractor
            article_data = universal_extractor(url, article_id=None, pmid=None)
            if "metadata" not in article_data:
                article_data["metadata"] = {}
            article_data["metadata"]["source"] = article.get("source", "unknown")
            
            self.cache["extracted_articles"][cache_key] = article_data
            self._save_cache()
            return article_data
        except Exception as e:
            logger.error(f"Error extracting article data from {url}: {e}")
            return {"metadata": {"title": "Extraction Failed", "source": article.get("source", "unknown")}, "full_text": ""}
    
    def process_with_gemini(self, disease_name: str, icd_code: str, articles_data: List[Dict]) -> Dict:
        """Process article data using Gemini 1.5 Flash API to extract structured information."""
        cache_key = f"{disease_name}_{icd_code}_processed"
        
        if cache_key in self.cache["processed_corpus"]:
            logger.info(f"Using cached processed data for {cache_key}")
            return self.cache["processed_corpus"][cache_key]
        
        combined_text = ""
        for article in articles_data:
            if article.get("full_text"):
                source_info = f"Source: {article.get('metadata', {}).get('source', 'unknown')}\n"
                title = article.get('metadata', {}).get('title', '')
                combined_text += source_info + (f"Title: {title}\n" if title else "") + article.get("full_text")[:8000] + "\n\n"
        
        if not combined_text:
            logger.warning(f"No text content found for {disease_name}")
            return self._create_empty_corpus_entry(disease_name, icd_code)
        
        prompt = f"""
        You are a medical expert assisting in creating a structured corpus of medical information.
        Extract detailed information about {disease_name} (ICD code: {icd_code}) from the following medical texts.
        Structure your response in a JSON format with the following keys:
        
        1. "disease": The disease name
        2. "icd_code": The ICD code
        3. "parameters": Dict containing:
           - "symptoms": List of symptoms with names, severities, and patterns
           - reversion": "1",
           - "vital_signs": Abnormal vital sign ranges
           - "physical_findings": List of physical examination findings
           - "lab_values": Dict of lab tests with abnormal ranges
           - "risk_factors": List of risk factors
           - "imaging_findings": Dict of imaging modalities and findings
        4. "diagnostic_criteria": Dict with required and supportive criteria
        5. "differential_diagnoses": List of alternative diagnoses
        
        Medical text:
        {combined_text}
        
        Output only valid JSON without additional text:
        """
        
        logger.info(f"Processing {disease_name} with Gemini 1.5 Flash")
        try:
            headers = {"Content-Type": "application/json", "x-goog-api-key": GOOGLE_API_KEY}
            payload = {
                "contents": [{"role": "user", "parts": [{"text": prompt}]}],
                "generationConfig": {"temperature": 0.2, "maxOutputTokens": 4096, "topP": 0.95, "topK": 40}
            }
            
            response = requests.post(GEMINI_API_URL, headers=headers, json=payload, timeout=10)
            response.raise_for_status()
            result = response.json()
            text = result.get("candidates", [{}])[0].get("content", {}).get("parts", [{}])[0].get("text", "")
            
            json_start, json_end = text.find("{"), text.rfind("}") + 1
            if json_start >= 0 and json_end > json_start:
                corpus_entry = json.loads(text[json_start:json_end])
                self._ensure_corpus_structure(corpus_entry, disease_name, icd_code)
                self.cache["processed_corpus"][cache_key] = corpus_entry
                self._save_cache()
                return corpus_entry
            else:
                logger.error(f"No JSON found in Gemini response")
        
        except Exception as e:
            logger.error(f"Error processing with Gemini: {e}")
        
        return self._create_empty_corpus_entry(disease_name, icd_code)
    
    def _ensure_corpus_structure(self, corpus_entry: Dict, disease_name: str, icd_code: str) -> None:
        """Ensure the corpus entry has the expected structure."""
        corpus_entry.setdefault("disease", disease_name)
        corpus_entry.setdefault("icd_code", icd_code)
        params = corpus_entry.setdefault("parameters", {})
        params.setdefault("symptoms", [])
        params.setdefault("vital_signs", {})
        params.setdefault("physical_findings", [])
        params.setdefault("lab_values", {})
        params.setdefault("risk_factors", [])
        params.setdefault("imaging_findings", {})
        corpus_entry.setdefault("diagnostic_criteria", {"required": [], "supportive": []})
        corpus_entry.setdefault("differential_diagnoses", [])
    
    def _create_empty_corpus_entry(self, disease_name: str, icd_code: str) -> Dict:
        """Create an empty corpus entry with the expected structure."""
        return {
            "disease": disease_name,
            "icd_code": icd_code,
            "parameters": {"symptoms": [], "vital_signs": {}, "physical_findings": [], "lab_values": {}, "risk_factors": [], "imaging_findings": {}},
            "diagnostic_criteria": {"required": [], "supportive": []},
            "differential_diagnoses": []
        }
    
    def build_corpus_for_disease(self, disease_name: str, icd_code: str) -> Dict:
        """Build a corpus entry for a single disease using Perplexity and universal_extractor."""
        logger.info(f"Building corpus for {disease_name} (ICD: {icd_code})")
        
        # Get links from Perplexity
        articles = self.search_perplexity(disease_name, icd_code)
        logger.info(f"Found {len(articles)} Perplexity-sourced articles for {disease_name}")
        
        if not articles:
            logger.warning(f"No articles found for {disease_name}")
            return self._create_empty_corpus_entry(disease_name, icd_code)
        
        # Extract data with universal_extractor
        articles_data = []
        with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
            future_to_article = {executor.submit(self.extract_article_data, article): article for article in articles}
            for future in concurrent.futures.as_completed(future_to_article):
                try:
                    article_data = future.result()
                    print(f'[ARTICLE DATA] {article_data}')
                    if article_data and article_data.get("full_text"):
                        articles_data.append(article_data)
                except Exception as e:
                    logger.error(f"Error processing {future_to_article[future]['url']}: {e}")
        
        logger.info(f"Successfully extracted {len(articles_data)} articles for {disease_name}")
        
        # Process with Gemini
        corpus_entry = self.process_with_gemini(disease_name, icd_code, articles_data)
        
        # Save to file
        output_file = os.path.join(OUTPUT_DIR, f"{icd_code}_{disease_name.replace(' ', '_')}.json")
        with open(output_file, 'w') as f:
            json.dump(corpus_entry, f, indent=4)
        
        logger.info(f"Saved corpus entry to {output_file}")
        return corpus_entry
    
    def build_corpus(self, diseases: List[Dict[str, str]]) -> Dict[str, Dict]:
        """Build a corpus for multiple diseases."""
        corpus = {}
        with concurrent.futures.ThreadPoolExecutor(max_workers=3) as executor:
            future_to_disease = {executor.submit(self.build_corpus_for_disease, d["disease"], d["icd_code"]): d for d in diseases}
            for future in tqdm(concurrent.futures.as_completed(future_to_disease), total=len(diseases)):
                disease = future_to_disease[future]
                try:
                    corpus[disease["icd_code"]] = future.result()
                except Exception as e:
                    logger.error(f"Error processing {disease['disease']}: {e}")
        return corpus

def parse_icd_codes_from_xlsx(file_path):
    """Parse all ICD codes and descriptions from an Excel file with no limit."""
    import pandas as pd
    
    diseases = []
    
    try:
        # Read the Excel file
        df = pd.read_excel(file_path)
        
        # Identify the columns based on the header info
        code_column = None
        description_column = None
        
        # Find the code and description columns
        for col in df.columns:
            if 'CODE' in str(col).upper():
                code_column = col
            elif 'DESCRIPTION' in str(col).upper() or 'DESC' in str(col).upper():
                description_column = col
        
        # If columns couldn't be automatically identified
        if code_column is None or description_column is None:
            # Try to use the first and second columns
            if len(df.columns) >= 2:
                code_column = df.columns[0]
                description_column = df.columns[1]
            else:
                raise ValueError("Could not identify CODE and DESCRIPTION columns")
        
        # Create disease entries for ALL rows
        for _, row in df.iterrows():
            code = str(row[code_column]).strip()
            description = str(row[description_column]).strip()
            
            # Skip empty rows or header rows
            if not code or code == 'nan' or code.upper() == 'CODE':
                continue
                
            diseases.append({"disease": description, "icd_code": code})
        
        logger.info(f"Successfully parsed {len(diseases)} ICD codes from Excel file")
        
    except Exception as e:
        logger.error(f"Error parsing ICD codes from Excel file: {e}")
        # Fallback to default diseases if file parsing fails
        diseases = [
            {"disease": "Congestive Heart Failure", "icd_code": "I50.9"},
            {"disease": "Type 2 Diabetes Mellitus", "icd_code": "E11"}
        ]
    
    return diseases

# def main():
#     # Read all diseases from the Excel file
#     icd_file_path = "/Users/hritvik/Downloads/section111validicd10-jan2025_0.xlsx"
#     all_diseases = parse_icd_codes_from_xlsx(icd_file_path)
    
#     # Find the index of "Other cerebrovascular syphilis"
#     start_index = -1
#     for i, disease in enumerate(all_diseases):
#         if "cerebrovascular syphilis" in disease["disease"].lower():
#             start_index = i
#             break
    
#     if start_index == -1:
#         logger.warning("Could not find 'Other cerebrovascular syphilis' in the dataset. Starting from beginning.")
#         start_index = 0
#     else:
#         # Start from the disease AFTER "Other cerebrovascular syphilis"
#         start_index += 1
#         logger.info(f"Found 'Other cerebrovascular syphilis' at index {start_index-1}. Starting from the next disease.")
    
#     # Get the remaining diseases to process
#     remaining_diseases = all_diseases[start_index:]
#     logger.info(f"Processing remaining {len(remaining_diseases)} diseases (out of {len(all_diseases)} total)")
    
#     # Process the remaining diseases
#     corpus_builder = MedicalCorpusBuilder()
#     corpus = corpus_builder.build_corpus(remaining_diseases)
    
#     # Save to file (append mode to avoid overwriting previous results)
#     output_file = os.path.join(OUTPUT_DIR, "complete_medical_corpus_continued.json")
#     with open(output_file, 'w') as f:
#         json.dump(corpus, f, indent=4)
    
#     logger.info(f"Medical corpus building continued and saved to {output_file}")

def main():
    # Read all diseases from the Excel file
    icd_file_path = "/Users/hritvik/Downloads/section111validicd10-jan2025_0.xlsx"
    all_diseases = parse_icd_codes_from_xlsx(icd_file_path)
    "last run INFO:__main__:Successfully extracted 4 articles for Merkel cell carcinoma of right lower limb, including hip"
    # Filter diseases to only include those with ICD codes starting with C or D
    c_and_d_diseases = []
    for disease in all_diseases:
        icd_code = disease["icd_code"]
        if icd_code.startswith('C') or icd_code.startswith('D'):
            c_and_d_diseases.append(disease)
    
    logger.info(f"Found {len(c_and_d_diseases)} diseases with ICD codes starting with C or D (out of {len(all_diseases)} total)")
    
    # Process the filtered diseases
    corpus_builder = MedicalCorpusBuilder()
    corpus = corpus_builder.build_corpus(c_and_d_diseases)
    
    # Save to file - keeping the original output directory and file name
    output_file = os.path.join(OUTPUT_DIR, "complete_medical_corpus_continued.json")
    with open(output_file, 'w') as f:
        json.dump(corpus, f, indent=4)
    
    logger.info(f"Medical corpus building continued and saved to {output_file}")

if __name__ == "__main__":
    main()