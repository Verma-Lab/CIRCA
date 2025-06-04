#!/usr/bin/env python3

from google.cloud import aiplatform

aiplatform.init(project="vermalab-gemini-psom-e3ea", location="us-central1")
endpoint = aiplatform.Endpoint(endpoint_name="projects/vermalab-gemini-psom-e3ea/locations/us-central1/endpoints/365720657142480896")

# Test data from your logs
current_node_doc = """NODE ID: node_0
NODE TYPE: dialogueNode
INSTRUCTION: When the user is at this dialogue node, display the message 'Welcome to Circa,  is it the first time, visiting circa' to the user.
FUNCTIONS:
- If user response matches or replied with or user intent matches with 'if user replied with yes', proceed to node node_1"""

message = "Hi"

# Extract functions part
functions_part = current_node_doc.split("FUNCTIONS:")[1] if "FUNCTIONS:" in current_node_doc else "None"

function_match_prompt = f"""
User message: "{message}"
Current node functions: {functions_part}

Does the user's message match any of the functions/conditions listed? 
Return only "MATCH" or "NO_MATCH"
"""

try:
    response = endpoint.predict(instances=[{"prompt": function_match_prompt}])
    match_response = response.predictions[0]
    
    if isinstance(match_response, str):
        match_response = match_response.strip()

    print(f"[FUNCTION MATCH CHECK] {match_response}")
    
except Exception as e:
    print(f"Error: {e}")