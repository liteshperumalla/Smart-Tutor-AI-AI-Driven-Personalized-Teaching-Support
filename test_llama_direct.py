#!/usr/bin/env python3
"""Test Llama model directly with Bedrock"""
import boto3
import json
import os
from dotenv import load_dotenv

load_dotenv()

# Initialize Bedrock client
client = boto3.client('bedrock-runtime', region_name='us-east-1')

# Test prompt
prompt = "What is Python? Explain in 2-3 sentences."

# Llama 3.3 request format
request_body = {
    "prompt": prompt,
    "max_gen_len": 512,
    "temperature": 0.7,
    "top_p": 0.9
}

print("Testing Llama 3.3 70B Instruct...")
print(f"Prompt: {prompt}\n")

try:
    response = client.invoke_model(
        modelId="meta.llama3-3-70b-instruct-v1:0",
        body=json.dumps(request_body)
    )

    response_body = json.loads(response['body'].read())
    print("Full Response Body:")
    print(json.dumps(response_body, indent=2))
    print("\n" + "="*60)

    # Try to get generated text
    generated_text = response_body.get('generation', '')
    print(f"\nGenerated text: {generated_text}")
    print(f"Text length: {len(generated_text)}")

except Exception as e:
    print(f"ERROR: {e}")
    import traceback
    traceback.print_exc()
