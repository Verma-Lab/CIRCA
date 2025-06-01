import os
from transformers import AutoTokenizer, AutoModelForCausalLM
import torch
from llama_index.core import Settings

def initialize_llm():
    model_path = "/persistent/models/llama-3.1-8b"
       
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

    # Set the LLM in Settings using a lambda function for generation
    Settings.llm = lambda x: model.generate(
        **tokenizer(x, return_tensors="pt").to("cuda"),
        max_new_tokens=512
       )

    return model, tokenizer

# Initialize the LLM when the script is imported
model, tokenizer = initialize_llm()