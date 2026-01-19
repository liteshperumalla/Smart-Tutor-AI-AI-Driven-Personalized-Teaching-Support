# RAG Pipeline Testing & Fine-Tuning - Quick Start Guide

**Purpose:** Test and optimize Phase 1 & 2 RAG improvements
**Date:** 2025-11-05
**Status:** Ready for Testing

---

## 🚀 Quick Start (5 Minutes)

### Step 1: Check System Readiness

```bash
python check_system.py
```

**Expected output:**
- ✅ Index files exist
- ✅ Evaluation dataset loaded (20 test cases)
- ✅ Configuration set
- ✅ Dependencies available
- ✅ Ollama service running

**If not ready:** Follow the fixes suggested by the check script

---

### Step 2: Run Quick Test (5 test cases)

```bash
# Test with current configuration
python test_rag_pipeline.py --limit 5

# View results
cat test_results.json | jq '.analysis'
```

**What to look for:**
- `avg_response_time`: Should be < 5s
- `avg_topic_coverage`: Should be > 0.70 (70%)
- `coverage_above_60`: Should be > 0.80 (80%)

---

### Step 3: Compare Configurations

```bash
# Test multiple configurations automatically
python test_rag_pipeline.py --mode compare

# This will test:
# 1. Baseline (Phase 1 only)
# 2. Phase 1 + 2 (All features)
# 3. Conservative CRAG (threshold=0.7)
# 4. Aggressive CRAG (threshold=0.3)
```

**What to look for:**
- Which config has best coverage?
- Which config is fastest?
- What's the trade-off?

---

## 📊 Understanding Results

### Sample Output

```json
{
  "analysis": {
    "total_tests": 5,
    "successful_tests": 5,
    "avg_response_time": 4.2,        // ✅ Good (< 5s)
    "avg_topic_coverage": 0.78,      // ✅ Good (> 70%)
    "coverage_above_80": 0.60,       // ⚠️  Acceptable (60% of queries)
    "coverage_above_60": 0.80,       // ✅ Good (80% of queries)
    "by_difficulty": {
      "easy": {"avg_coverage": 0.85, "count": 2},
      "medium": {"avg_coverage": 0.75, "count": 2},
      "hard": {"avg_coverage": 0.70, "count": 1}
    }
  }
}
```

### Metrics Interpretation

| Metric | Excellent | Good | Acceptable | Poor |
|--------|-----------|------|------------|------|
| **avg_response_time** | < 3s | 3-4s | 4-6s | > 6s |
| **avg_topic_coverage** | > 85% | 70-85% | 60-70% | < 60% |
| **coverage_above_80** | > 80% | 60-80% | 40-60% | < 40% |
| **coverage_above_60** | > 90% | 80-90% | 70-80% | < 70% |

---

## 🔧 Common Fine-Tuning Scenarios

### Scenario 1: "Queries are too slow"

**Symptom:** avg_response_time > 5s

**Solution:**
```bash
# Option A: Disable query rewriting (saves ~300ms)
export QUERY_REWRITING_ENABLED=false
python test_rag_pipeline.py --limit 5

# Option B: Reduce query expansions (saves ~100ms)
export QUERY_EXPANSION_NUM=2
python test_rag_pipeline.py --limit 5

# Option C: Disable Self-RAG (saves ~400ms, not recommended)
export SELF_RAG_ENABLED=false
python test_rag_pipeline.py --limit 5
```

**Expected impact:**
- Option A: -300ms, -10% coverage
- Option B: -100ms, -5% coverage
- Option C: -400ms, +hallucinations

---

### Scenario 2: "Coverage is too low"

**Symptom:** avg_topic_coverage < 70%

**Solution:**
```bash
# Option A: Lower CRAG threshold (trigger more web searches)
export CRAG_QUALITY_THRESHOLD=0.3
python test_rag_pipeline.py --limit 5

# Option B: Increase query expansions
export QUERY_EXPANSION_NUM=4
python test_rag_pipeline.py --limit 5

# Option C: Check if you need better documents
python check_system.py  # Verify index exists
```

**Expected impact:**
- Option A: +10-15% coverage, +web search usage
- Option B: +5-10% coverage, +200ms latency

---

### Scenario 3: "Too many web searches"

**Symptom:** >30% of queries trigger web search (check logs)

**Solution:**
```bash
# Raise CRAG threshold
export CRAG_QUALITY_THRESHOLD=0.7
python test_rag_pipeline.py --limit 5

# Check if local knowledge base is complete
ls -lh persisted_index/
ls -lh chroma_db/
```

---

### Scenario 4: "Inconsistent quality"

**Symptom:** Some queries great (>90%), others poor (<40%)

**Solution:**
```bash
# Run full test to identify problem categories
python test_rag_pipeline.py

# Check which categories fail
cat test_results.json | jq '.analysis.by_category'

# Check specific failing tests
cat test_results.json | jq '.results[] | select(.topic_coverage < 0.5)'
```

Then:
- Add more documents for weak categories
- Improve parsing for specific file types
- Consider category-specific tuning

---

## 📈 Recommended Testing Workflow

### Week 1: Baseline & Quick Wins

**Day 1-2: Establish Baseline**
```bash
# 1. Check system
python check_system.py

# 2. Run baseline (Phase 1 only)
export QUERY_REWRITING_ENABLED=false
export SELF_RAG_ENABLED=false
python test_rag_pipeline.py --output baseline_phase1.json

# 3. Run with Phase 2
export QUERY_REWRITING_ENABLED=true
export SELF_RAG_ENABLED=true
python test_rag_pipeline.py --output baseline_phase2.json

# 4. Compare
echo "Phase 1 coverage: $(jq '.analysis.avg_topic_coverage' baseline_phase1.json)"
echo "Phase 2 coverage: $(jq '.analysis.avg_topic_coverage' baseline_phase2.json)"
```

**Day 3-4: Quick Tuning**
```bash
# Test different CRAG thresholds
for threshold in 0.3 0.4 0.5 0.6 0.7; do
    export CRAG_QUALITY_THRESHOLD=$threshold
    python test_rag_pipeline.py --limit 10 --output "test_crag_${threshold}.json"
done

# Find best threshold
for file in test_crag_*.json; do
    echo "$file: $(jq '.analysis.avg_topic_coverage' $file)"
done
```

**Day 5: Production Config**
```bash
# Set optimal configuration
export CRAG_QUALITY_THRESHOLD=0.5  # Adjust based on your tests
export QUERY_EXPANSION_NUM=3
export QUERY_REWRITING_ENABLED=true
export SELF_RAG_ENABLED=true

# Run full validation
python test_rag_pipeline.py --output production_ready.json
```

---

### Week 2: Production Monitoring

**Enable Evaluation Logging:**
```bash
# In .env or environment
export EVALUATION_ENABLED=true

# Run your application normally
# Metrics will be logged to logs/rag_evaluation.jsonl
```

**Daily Checks:**
```bash
# View last 50 queries
tail -n 50 logs/rag_evaluation.jsonl | jq '.metadata.reflection'

# Calculate daily averages
cat logs/rag_evaluation.jsonl | \
  jq -r '.retrieval_metrics.retrieval_time_seconds' | \
  awk '{sum+=$1; count++} END {print "Avg retrieval:", sum/count, "s"}'
```

**Weekly Review:**
```bash
# Get summary stats
python -c "
from backend.rag_evaluation import get_evaluator
evaluator = get_evaluator()
stats = evaluator.get_summary_stats(last_n=500)
import json
print(json.dumps(stats, indent=2))
"
```

---

## 🎯 Target Metrics (Production-Ready)

| Metric | Target | Current | Status |
|--------|--------|---------|--------|
| Avg Response Time | < 4s | _TBD_ | ⏱️ |
| P95 Response Time | < 6s | _TBD_ | ⏱️ |
| Avg Topic Coverage | > 80% | _TBD_ | 📊 |
| Coverage ≥60% | > 90% | _TBD_ | 📊 |
| Success Rate | > 95% | _TBD_ | ✅ |

**How to measure:**
```bash
# Run full test suite
python test_rag_pipeline.py

# Extract metrics
jq '.analysis | {
  avg_time: .avg_response_time,
  p95_time: .p95_response_time,
  avg_coverage: .avg_topic_coverage,
  coverage_60_plus: .coverage_above_60,
  success_rate: (.successful_tests / .total_tests)
}' test_results.json
```

---

## 🛠️ Available Tools

### 1. `check_system.py` - System Readiness Check
**Purpose:** Verify all components are configured correctly
**Usage:** `python check_system.py`
**When to use:** Before starting any testing

### 2. `test_rag_pipeline.py` - Main Testing Tool
**Purpose:** Run evaluation dataset and benchmark performance
**Usage:**
```bash
# Quick test (5 queries)
python test_rag_pipeline.py --limit 5

# Full test (20 queries)
python test_rag_pipeline.py

# Compare configurations
python test_rag_pipeline.py --mode compare

# Custom output file
python test_rag_pipeline.py --output my_results.json
```

### 3. `FINE_TUNING_GUIDE.md` - Comprehensive Guide
**Purpose:** Detailed tuning instructions and parameter explanations
**Usage:** `cat FINE_TUNING_GUIDE.md | less`
**When to use:** When you need detailed parameter information

### 4. `evaluation_dataset.json` - Test Cases
**Purpose:** 20 gold-standard test cases for benchmarking
**Categories:** factual, conceptual, procedural, advanced, ambiguous
**Usage:** Automatically used by test_rag_pipeline.py

---

## 📝 Configuration Files

### Environment Variables (Recommended)

Create a `.env` file:
```bash
# Phase 1 Settings
CHUNK_SIZE=512
CHUNK_OVERLAP=102
EMBEDDING_MODEL=BAAI/bge-small-en-v1.5
QUERY_EXPANSION_ENABLED=true
QUERY_EXPANSION_NUM=3

# Phase 2 Settings
QUERY_REWRITING_ENABLED=true
SELF_RAG_ENABLED=true
CRAG_QUALITY_THRESHOLD=0.5

# Evaluation
EVALUATION_ENABLED=true
EVALUATION_LOG_FILE=logs/rag_evaluation.jsonl
```

Then load with: `source .env` or use `python-dotenv`

---

## 🐛 Troubleshooting

### "No module named 'llama_index'"
```bash
pip install -r requirements.txt
```

### "Index not found at ./persisted_index"
```bash
python Data_parsing.py
```

### "Ollama service not accessible"
```bash
# Start Ollama
ollama serve

# In another terminal, verify
ollama list
```

### "Test script hangs"
```bash
# Check if Ollama is responding
curl http://localhost:11434/api/tags

# Reduce timeout in test script if needed
# Or test with fewer queries
python test_rag_pipeline.py --limit 3
```

### "Low coverage despite good config"
```bash
# Check if documents are indexed
ls -lh persisted_index/
ls -lh chroma_db/

# Verify documents exist
ls -lh data/  # or wherever your documents are

# Re-index if needed
rm -rf persisted_index/* chroma_db/*
python Data_parsing.py
```

---

## 📚 Additional Resources

### Documentation Files
- `PHASE1_IMPROVEMENTS.md` - Phase 1 features and benefits
- `PHASE2_IMPROVEMENTS.md` - Phase 2 features and benefits
- `FINE_TUNING_GUIDE.md` - Detailed parameter tuning guide
- `README.md` - Project overview

### Evaluation Logs
- `logs/rag_evaluation.jsonl` - Continuous query metrics
- `test_results.json` - Latest test results
- `test_results_*.json` - Historical test results

---

## 🎓 Next Steps

After testing and tuning:

1. ✅ **Achieve target metrics** (see Target Metrics section)
2. 📊 **Enable production monitoring** (`EVALUATION_ENABLED=true`)
3. 👥 **Deploy to users** with confidence
4. 📈 **Monitor continuously** and adjust parameters
5. 🚀 **Consider Phase 3** when ready (Context & Quality improvements)

---

## ✅ Success Checklist

Before considering testing complete:

- [ ] System check passes (`python check_system.py`)
- [ ] Baseline test run (Phase 1 only)
- [ ] Full features test run (Phase 1 + 2)
- [ ] Configuration comparison done
- [ ] Optimal CRAG threshold identified
- [ ] Target metrics achieved
- [ ] Production monitoring enabled
- [ ] Documentation reviewed

---

## 💡 Pro Tips

1. **Start small:** Test with `--limit 5` before running full suite
2. **Compare apples to apples:** Use same test cases when comparing configs
3. **Watch the logs:** `tail -f logs/rag_evaluation.jsonl | jq .metadata.reflection`
4. **Iterate quickly:** Small parameter changes, test, adjust
5. **Document findings:** Keep notes on what works for your use case
6. **Monitor in production:** Don't just test once, monitor continuously

---

**Testing Status:** ✅ Tools Ready - Start Testing!

**Commands to run right now:**
```bash
# 1. Check system
python check_system.py

# 2. Quick test
python test_rag_pipeline.py --limit 5

# 3. Review guide
cat FINE_TUNING_GUIDE.md | less
```

---

*Last Updated: 2025-11-05*
*Version: 1.0*
*Compatible with: Phase 1 & 2 improvements*
