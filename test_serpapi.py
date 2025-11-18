#!/usr/bin/env python3
import os
from dotenv import load_dotenv
load_dotenv()

# Import Tutor_chat to check SERPAPI_AVAILABLE
import Tutor_chat

print(f"SERPAPI_AVAILABLE: {Tutor_chat.SERPAPI_AVAILABLE}")
print(f"SERPAPI_API_KEY exists: {bool(Tutor_chat.SERPAPI_API_KEY)}")
print(f"REQUESTS_AVAILABLE: {Tutor_chat.REQUESTS_AVAILABLE}")

# Test WebSearchAgent
agent = Tutor_chat.WebSearchAgent()
print(f"\nWebSearchAgent.serpapi_available: {agent.serpapi_available}")
print(f"WebSearchAgent.requests_available: {agent.requests_available}")

# Try a search
print("\nPerforming test search...")
results = agent.search_web("Python programming", max_results=1)

if results:
    print(f"✓ Got {len(results)} result(s)")
    print(f"First result title: {results[0].get('title', 'N/A')[:50]}")
    print(f"Source: {'SerpAPI' if agent.serpapi_available else 'DuckDuckGo fallback'}")
else:
    print("✗ No results returned")
