import os
from transformers import AutoTokenizer, AutoModelForCausalLM
import torch
from llama_index.core import Settings
from llama_index.core.llms import LLM

class LLaMA3_1LLM(LLM):
    def __init__(self, model, tokenizer):
        self.model = model
        self.tokenizer = tokenizer

    def complete(self, prompt, **kwargs):
        inputs = self.tokenizer(prompt, return_tensors="pt").to("cuda")
        outputs = self.model.generate(**inputs, max_new_tokens=512, **kwargs)
        return self.tokenizer.decode(outputs[0], skip_special_tokens=True)

    def stream_complete(self, prompt, **kwargs):
        # Simple streaming implementation (can be enhanced)
        inputs = self.tokenizer(prompt, return_tensors="pt").to("cuda")
        for output in self.model.generate(**inputs, max_new_tokens=512, **kwargs):
            yield self.tokenizer.decode(output, skip_special_tokens=True)

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
    Settings.llm = llm

    return model, tokenizer

# Initialize the LLM when the script is imported
model, tokenizer = initialize_llm()