#!/usr/bin/env python3
import boto3
import sys
sys.path.insert(0, '/Users/liteshperumalla/Desktop/Files/masters/Smart AI Tutor')
from backend.config import config

print("Listing available Bedrock models in us-east-1...")
print("=" * 70)

client = boto3.client('bedrock', region_name='us-east-1')

try:
    # List foundation models
    response = client.list_foundation_models()
    
    print(f"\nFound {len(response['modelSummaries'])} models\n")
    
    # Filter for Meta Llama and Amazon Titan
    for model in response['modelSummaries']:
        if 'llama' in model['modelId'].lower() or 'titan' in model['modelId'].lower():
            print(f"Model: {model['modelId']}")
            print(f"  Provider: {model['providerName']}")
            print(f"  Name: {model['modelName']}")
            if 'inferenceTypesSupported' in model:
                print(f"  Inference: {model['inferenceTypesSupported']}")
            print()
            
except Exception as e:
    print(f"Error: {e}")

print("=" * 70)
