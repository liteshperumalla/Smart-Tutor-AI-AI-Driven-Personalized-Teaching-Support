#!/usr/bin/env python3
"""
System Readiness Check for RAG Pipeline Testing
Verifies all components are properly configured
"""

import os
import sys
from pathlib import Path
import json

def check_mark(condition):
    return "✅" if condition else "❌"

def main():
    print("🔍 RAG Pipeline System Check")
    print("="*60)

    all_good = True

    # 1. Check index exists
    print("\n📁 Index Files:")
    persist_dir = Path("./persisted_index")
    chroma_dir = Path("./chroma_db")

    persist_exists = persist_dir.exists() and any(persist_dir.iterdir())
    chroma_exists = chroma_dir.exists() and any(chroma_dir.iterdir())

    print(f"   {check_mark(persist_exists)} Persisted index: {persist_dir}")
    print(f"   {check_mark(chroma_exists)} ChromaDB: {chroma_dir}")

    if not persist_exists or not chroma_exists:
        print("   ⚠️  Run 'python Data_parsing.py' to create index")
        all_good = False

    # 2. Check evaluation dataset
    print("\n📊 Evaluation Dataset:")
    eval_dataset = Path("evaluation_dataset.json")
    eval_exists = eval_dataset.exists()

    print(f"   {check_mark(eval_exists)} {eval_dataset}")

    if eval_exists:
        with open(eval_dataset) as f:
            data = json.load(f)
            test_count = len(data.get('test_cases', []))
            print(f"      {test_count} test cases loaded")
    else:
        all_good = False

    # 3. Check configuration
    print("\n⚙️  Configuration:")
    config_items = [
        ("QUERY_REWRITING_ENABLED", os.getenv("QUERY_REWRITING_ENABLED", "true")),
        ("SELF_RAG_ENABLED", os.getenv("SELF_RAG_ENABLED", "true")),
        ("QUERY_EXPANSION_ENABLED", os.getenv("QUERY_EXPANSION_ENABLED", "true")),
        ("QUERY_EXPANSION_NUM", os.getenv("QUERY_EXPANSION_NUM", "3")),
        ("CRAG_QUALITY_THRESHOLD", os.getenv("CRAG_QUALITY_THRESHOLD", "0.5")),
        ("CHUNK_SIZE", os.getenv("CHUNK_SIZE", "512")),
        ("CHUNK_OVERLAP", os.getenv("CHUNK_OVERLAP", "102")),
    ]

    for key, value in config_items:
        print(f"   • {key:30} = {value}")

    # 4. Check Python dependencies
    print("\n📦 Dependencies:")
    required_modules = [
        "llama_index",
        "chromadb",
        "sentence_transformers",
        "ollama",
    ]

    for module in required_modules:
        try:
            __import__(module)
            print(f"   {check_mark(True)} {module}")
        except ImportError:
            print(f"   {check_mark(False)} {module} (missing)")
            all_good = False

    # 5. Check Ollama service
    print("\n🤖 LLM Service:")
    try:
        import requests
        response = requests.get("http://localhost:11434/api/tags", timeout=2)
        if response.status_code == 200:
            models = response.json().get('models', [])
            print(f"   ✅ Ollama service running")
            if models:
                print(f"      {len(models)} models available:")
                for model in models[:3]:
                    print(f"        - {model['name']}")
        else:
            print(f"   ❌ Ollama service not responding")
            all_good = False
    except Exception as e:
        print(f"   ❌ Ollama service not accessible: {e}")
        print(f"      Start with: ollama serve")
        all_good = False

    # 6. Check logs directory
    print("\n📝 Logging:")
    logs_dir = Path("logs")
    logs_dir.mkdir(exist_ok=True)
    print(f"   {check_mark(True)} Logs directory: {logs_dir}")

    eval_log = logs_dir / "rag_evaluation.jsonl"
    if eval_log.exists():
        line_count = sum(1 for _ in open(eval_log))
        print(f"      {line_count} entries in evaluation log")
    else:
        print(f"      No evaluation log yet (will be created)")

    # 7. Check testing scripts
    print("\n🧪 Testing Tools:")
    test_script = Path("test_rag_pipeline.py")
    test_exists = test_script.exists()
    print(f"   {check_mark(test_exists)} {test_script}")

    fine_tune_guide = Path("FINE_TUNING_GUIDE.md")
    guide_exists = fine_tune_guide.exists()
    print(f"   {check_mark(guide_exists)} {fine_tune_guide}")

    # Summary
    print("\n" + "="*60)
    if all_good:
        print("✅ System is ready for testing!")
        print("\nNext steps:")
        print("  1. Quick test:    python test_rag_pipeline.py --limit 5")
        print("  2. Full test:     python test_rag_pipeline.py")
        print("  3. Compare configs: python test_rag_pipeline.py --mode compare")
        print("  4. Read guide:    cat FINE_TUNING_GUIDE.md")
    else:
        print("⚠️  System is not fully ready")
        print("\nPlease address the issues marked with ❌ above")
        print("\nCommon fixes:")
        print("  • Missing index: python Data_parsing.py")
        print("  • Missing Ollama: ollama serve")
        print("  • Missing deps: pip install -r requirements.txt")

    print("="*60)
    return 0 if all_good else 1

if __name__ == "__main__":
    sys.exit(main())
