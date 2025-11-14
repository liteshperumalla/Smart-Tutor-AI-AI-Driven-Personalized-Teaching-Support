# RAG Pipeline Fine-Tuning Guide

**Purpose:** Optimize Phase 1 & 2 improvements for your specific use case
**Date:** 2025-11-05
**Version:** 1.0

---

## Quick Start

```bash
# 1. Run baseline tests
python test_rag_pipeline.py --mode single --limit 10

# 2. Compare configurations
python test_rag_pipeline.py --mode compare

# 3. Analyze results
cat test_results.json | jq '.analysis'

# 4. Fine-tune parameters
# (See Parameter Tuning section below)
```

---

## Understanding the Metrics

### 1. **Response Time**
- **Avg response time:** Mean time for all queries
- **Median response time:** Middle value (more stable than mean)
- **P95 response time:** 95th percentile (worst-case scenarios)

**Targets:**
- ✅ Good: < 4s avg, < 6s P95
- ⚠️ Acceptable: 4-6s avg, 6-8s P95
- ❌ Poor: > 6s avg, > 8s P95

**If too slow:**
- Disable query rewriting: `export QUERY_REWRITING_ENABLED=false` (saves ~300ms)
- Disable Self-RAG: `export SELF_RAG_ENABLED=false` (saves ~400ms)
- Reduce query expansions: `export QUERY_EXPANSION_NUM=2` (saves ~100ms)

---

### 2. **Topic Coverage**
- **Avg topic coverage:** % of expected topics mentioned in responses
- **Median topic coverage:** Middle value
- **Coverage ≥80%:** % of queries covering most topics
- **Coverage ≥60%:** % of queries covering majority of topics

**Targets:**
- ✅ Excellent: > 80% avg coverage
- ✅ Good: 70-80% avg coverage
- ⚠️ Acceptable: 60-70% avg coverage
- ❌ Poor: < 60% avg coverage

**If coverage is low:**
- Increase retrieval: `export SIMILARITY_TOP_K=5`
- Lower CRAG threshold: `export CRAG_QUALITY_THRESHOLD=0.4` (more web searches)
- Check if index has relevant documents
- Re-run Data_parsing.py with updated documents

---

### 3. **By Difficulty**
Shows performance across difficulty levels:
- **easy:** Should be >85% coverage
- **medium:** Should be >75% coverage
- **hard:** Should be >65% coverage
- **very_hard:** Should be >50% coverage

**If hard queries fail:**
- Enable multi-hop reasoning (future feature)
- Increase context window
- Improve chunking (already optimized in Phase 1)

---

### 4. **By Category**
Shows performance by query type:
- **factual:** Simple definitions (should be highest)
- **conceptual:** Understanding relationships
- **procedural:** Step-by-step instructions
- **advanced:** Complex topics
- **ambiguous:** Tests query rewriting effectiveness

**If ambiguous queries fail:**
- Ensure query rewriting is enabled
- Check logs for rewritten queries
- May need to improve rewriting prompt

---

## Parameter Tuning

### 1. **CRAG_QUALITY_THRESHOLD** (Most Important)

**What it controls:** When to trigger web search
**Range:** 0.0 - 1.0
**Default:** 0.5

| Value | Behavior | Use Case |
|-------|----------|----------|
| 0.3 | Aggressive web search | Incomplete local knowledge base |
| 0.5 | Balanced (default) | Good local knowledge, occasional gaps |
| 0.7 | Conservative | Comprehensive local knowledge |

**Tuning steps:**

```bash
# Test baseline
export CRAG_QUALITY_THRESHOLD=0.5
python test_rag_pipeline.py --limit 5

# Try aggressive (more web searches)
export CRAG_QUALITY_THRESHOLD=0.3
python test_rag_pipeline.py --limit 5

# Try conservative (fewer web searches)
export CRAG_QUALITY_THRESHOLD=0.7
python test_rag_pipeline.py --limit 5

# Compare results
cat test_results*.json | jq '.analysis.avg_topic_coverage'
```

**Recommendation:**
- Start with 0.5
- If coverage < 70%, try 0.4
- If coverage > 85% but many web searches, try 0.6

---

### 2. **QUERY_EXPANSION_NUM**

**What it controls:** Number of query variations
**Range:** 1 - 5
**Default:** 3

| Value | Impact | Latency | Use Case |
|-------|--------|---------|----------|
| 1 | No expansion | Fast | Clear, specific queries |
| 2 | Minimal expansion | +100ms | Good knowledge base |
| 3 | Balanced (default) | +200ms | General use |
| 5 | Maximum coverage | +400ms | Sparse knowledge base |

**Tuning steps:**

```bash
# Test with fewer expansions (faster)
export QUERY_EXPANSION_NUM=2
python test_rag_pipeline.py --limit 5

# Test with more expansions (better coverage)
export QUERY_EXPANSION_NUM=4
python test_rag_pipeline.py --limit 5
```

**Recommendation:**
- Start with 3
- If latency > 5s, try 2
- If coverage < 70%, try 4

---

### 3. **CHUNK_SIZE & CHUNK_OVERLAP**

**What it controls:** Document chunking strategy
**Default:** 512 chars, 102 overlap (20%)

| Chunk Size | Use Case | Re-index Required |
|------------|----------|-------------------|
| 256 | Small documents, precise retrieval | Yes |
| 512 | Balanced (default) | Yes |
| 768 | Long documents, more context | Yes |
| 1024 | Maximum context | Yes |

**⚠️ Changing these requires re-indexing:**

```bash
# 1. Update config
export CHUNK_SIZE=768
export CHUNK_OVERLAP=154  # 20% of 768

# 2. Delete old index
rm -rf ./persisted_index/*
rm -rf ./chroma_db/*

# 3. Re-run parsing
python Data_parsing.py

# 4. Test
python test_rag_pipeline.py --limit 5
```

**Recommendation:**
- Keep at 512 unless you have specific needs
- Larger chunks = more context but slower retrieval
- Smaller chunks = faster but may miss context

---

### 4. **Feature Toggles**

**QUERY_REWRITING_ENABLED**
- Default: `true`
- Impact: +200-400ms latency, +10-15% coverage
- Disable if: Latency is critical and queries are already clear

**SELF_RAG_ENABLED**
- Default: `true`
- Impact: +300-500ms latency, -52% hallucinations
- Disable if: Latency is critical (not recommended)

**QUERY_EXPANSION_ENABLED**
- Default: `true`
- Impact: +8-15% recall
- Disable if: Only specific, clear queries expected

---

## Testing Workflows

### Workflow 1: Quick Validation (5 minutes)

```bash
# Run 5 test cases with current config
python test_rag_pipeline.py --limit 5

# Check key metrics
cat test_results.json | jq '{
  avg_time: .analysis.avg_response_time,
  avg_coverage: .analysis.avg_topic_coverage,
  success_rate: .analysis.coverage_above_60
}'
```

**Success criteria:**
- ✅ avg_time < 5s
- ✅ avg_coverage > 0.7
- ✅ success_rate > 0.8

---

### Workflow 2: Configuration Comparison (15 minutes)

```bash
# Compare 4 configurations
python test_rag_pipeline.py --mode compare

# View comparison table
# (automatically printed at end)
```

**Interpret results:**
- Look for best balance of speed and coverage
- Check which config works best for your use case

---

### Workflow 3: Full Evaluation (30 minutes)

```bash
# Run all 20 test cases
python test_rag_pipeline.py --mode single

# Deep dive into results
cat test_results.json | jq '.results[] | select(.topic_coverage < 0.6)'

# Find problematic categories
cat test_results.json | jq '.analysis.by_category'
```

**Action items:**
- Identify failing categories
- Check if specific document types need better parsing
- Consider adding more training data for weak categories

---

### Workflow 4: Latency Optimization (10 minutes)

```bash
# Baseline (all features)
export QUERY_REWRITING_ENABLED=true
export SELF_RAG_ENABLED=true
export QUERY_EXPANSION_NUM=3
time python test_rag_pipeline.py --limit 3

# Speed optimization
export QUERY_REWRITING_ENABLED=false  # Save ~300ms
export SELF_RAG_ENABLED=false         # Save ~400ms
export QUERY_EXPANSION_NUM=2          # Save ~100ms
time python test_rag_pipeline.py --limit 3

# Compare times
```

**Target:** < 3s per query with optimization

---

### Workflow 5: Quality Optimization (20 minutes)

```bash
# Baseline
export CRAG_QUALITY_THRESHOLD=0.5
python test_rag_pipeline.py --limit 10 --output baseline.json

# More aggressive retrieval
export CRAG_QUALITY_THRESHOLD=0.3
export QUERY_EXPANSION_NUM=4
python test_rag_pipeline.py --limit 10 --output aggressive.json

# Compare coverage
diff <(jq '.analysis.avg_topic_coverage' baseline.json) \
     <(jq '.analysis.avg_topic_coverage' aggressive.json)
```

---

## Monitoring in Production

### 1. **Set up continuous monitoring**

```bash
# Enable evaluation logging
export EVALUATION_ENABLED=true

# Run your application normally
# Metrics will be logged to logs/rag_evaluation.jsonl
```

### 2. **Daily metrics check**

```bash
# Get last 100 queries
tail -n 100 logs/rag_evaluation.jsonl > daily.jsonl

# Calculate averages
cat daily.jsonl | jq -r '.retrieval_metrics.retrieval_time_seconds' | \
  awk '{sum+=$1; count++} END {print "Avg retrieval time:", sum/count, "s"}'

cat daily.jsonl | jq -r '.metadata.reflection.relevance_score' | \
  awk '{sum+=$1; count++} END {print "Avg relevance score:", sum/count}'
```

### 3. **Weekly review**

```bash
# Analyze trends
python -c "
from backend.rag_evaluation import get_evaluator
evaluator = get_evaluator()
stats = evaluator.get_summary_stats(last_n=500)
import json
print(json.dumps(stats, indent=2))
"
```

---

## Common Issues & Solutions

### Issue 1: High Latency (>6s avg)

**Symptoms:**
- P95 response time > 8s
- User complaints about slowness

**Solutions:**
1. Disable query rewriting: `export QUERY_REWRITING_ENABLED=false`
2. Reduce expansions: `export QUERY_EXPANSION_NUM=2`
3. Use faster LLM for preprocessing (code change needed)
4. Cache common queries (future feature)

**Trade-offs:**
- -300ms latency, -10% coverage (no rewriting)
- -100ms latency, -5% coverage (fewer expansions)

---

### Issue 2: Low Coverage (<60%)

**Symptoms:**
- Many queries below 60% topic coverage
- Users reporting incomplete answers

**Solutions:**
1. Lower CRAG threshold: `export CRAG_QUALITY_THRESHOLD=0.3`
2. Increase expansions: `export QUERY_EXPANSION_NUM=4`
3. Check if documents are in index: `ls -lh persisted_index/`
4. Re-index with better chunking
5. Add more documents to knowledge base

---

### Issue 3: Too Many Web Searches

**Symptoms:**
- >30% of queries trigger web search
- High API costs (if using paid search API)

**Solutions:**
1. Raise CRAG threshold: `export CRAG_QUALITY_THRESHOLD=0.7`
2. Improve local knowledge base
3. Re-index with larger chunks: `export CHUNK_SIZE=768`
4. Check Self-RAG reflection scores in logs

---

### Issue 4: Inconsistent Quality

**Symptoms:**
- Some queries excellent (>90%), others poor (<40%)
- High variance in topic coverage

**Solutions:**
1. Analyze by category: Check which types fail
2. Add documents for weak categories
3. Tune per-category parameters (future feature)
4. Enable more aggressive retrieval for all queries

---

### Issue 5: Hallucinations

**Symptoms:**
- Responses contain incorrect information
- Information not in source documents

**Solutions:**
1. **Ensure Self-RAG is enabled:** `export SELF_RAG_ENABLED=true`
2. Check reflection confidence in logs
3. Increase MIN_RERANK_SCORE: `export MIN_RERANK_SCORE=0.3`
4. Review source documents for quality
5. Enable stricter CRAG: `export CRAG_QUALITY_THRESHOLD=0.6`

**Expected improvement:** -52% with Self-RAG enabled

---

## Recommended Configurations

### Configuration A: Balanced (Default)
**Best for:** General use, good knowledge base

```bash
export QUERY_REWRITING_ENABLED=true
export SELF_RAG_ENABLED=true
export QUERY_EXPANSION_ENABLED=true
export QUERY_EXPANSION_NUM=3
export CRAG_QUALITY_THRESHOLD=0.5
export CHUNK_SIZE=512
export CHUNK_OVERLAP=102
```

**Expected:**
- Latency: 4-5s avg
- Coverage: 75-85%
- Hallucinations: Low

---

### Configuration B: Speed Optimized
**Best for:** Real-time applications, latency-critical

```bash
export QUERY_REWRITING_ENABLED=false
export SELF_RAG_ENABLED=false
export QUERY_EXPANSION_ENABLED=true
export QUERY_EXPANSION_NUM=2
export CRAG_QUALITY_THRESHOLD=0.6
export CHUNK_SIZE=512
export CHUNK_OVERLAP=102
```

**Expected:**
- Latency: 2-3s avg
- Coverage: 65-75%
- Hallucinations: Medium

---

### Configuration C: Quality Optimized
**Best for:** Accuracy-critical, research applications

```bash
export QUERY_REWRITING_ENABLED=true
export SELF_RAG_ENABLED=true
export QUERY_EXPANSION_ENABLED=true
export QUERY_EXPANSION_NUM=4
export CRAG_QUALITY_THRESHOLD=0.4
export CHUNK_SIZE=768
export CHUNK_OVERLAP=154
```

**Expected:**
- Latency: 5-7s avg
- Coverage: 85-95%
- Hallucinations: Very Low

---

### Configuration D: Minimal (Baseline)
**Best for:** Testing, debugging

```bash
export QUERY_REWRITING_ENABLED=false
export SELF_RAG_ENABLED=false
export QUERY_EXPANSION_ENABLED=false
export CRAG_QUALITY_THRESHOLD=0.5
export CHUNK_SIZE=512
export CHUNK_OVERLAP=102
```

**Expected:**
- Latency: 2s avg
- Coverage: 55-65%
- Hallucinations: High

---

## Advanced Tuning

### A/B Testing

```bash
# Create two configuration files
cat > config_a.env <<EOF
QUERY_REWRITING_ENABLED=true
SELF_RAG_ENABLED=true
CRAG_QUALITY_THRESHOLD=0.5
EOF

cat > config_b.env <<EOF
QUERY_REWRITING_ENABLED=true
SELF_RAG_ENABLED=true
CRAG_QUALITY_THRESHOLD=0.4
EOF

# Test configuration A
source config_a.env
python test_rag_pipeline.py --output results_a.json

# Test configuration B
source config_b.env
python test_rag_pipeline.py --output results_b.json

# Compare
echo "Config A coverage: $(jq '.analysis.avg_topic_coverage' results_a.json)"
echo "Config B coverage: $(jq '.analysis.avg_topic_coverage' results_b.json)"
```

---

### Parameter Grid Search

```bash
#!/bin/bash
# Test multiple threshold values

for threshold in 0.3 0.4 0.5 0.6 0.7; do
    echo "Testing threshold=$threshold"
    export CRAG_QUALITY_THRESHOLD=$threshold
    python test_rag_pipeline.py --limit 10 --output "results_${threshold}.json"

    coverage=$(jq '.analysis.avg_topic_coverage' "results_${threshold}.json")
    time=$(jq '.analysis.avg_response_time' "results_${threshold}.json")

    echo "Threshold=$threshold -> Coverage=$coverage, Time=$time"
done

# Find best threshold
```

---

## Success Criteria

### Production-Ready Metrics

| Metric | Target | Acceptable | Poor |
|--------|--------|------------|------|
| Avg Response Time | < 4s | 4-6s | > 6s |
| P95 Response Time | < 6s | 6-8s | > 8s |
| Avg Topic Coverage | > 80% | 70-80% | < 70% |
| Coverage ≥60% | > 90% | 80-90% | < 80% |
| Failed Queries | < 5% | 5-10% | > 10% |

### Quality Targets by Difficulty

| Difficulty | Target Coverage |
|------------|-----------------|
| Easy | > 90% |
| Medium | > 80% |
| Hard | > 70% |
| Very Hard | > 60% |

---

## Next Steps

After fine-tuning:

1. ✅ **Validate in production** with real users for 1 week
2. 📊 **Monitor metrics** daily using evaluation logs
3. 🔄 **Iterate** on parameters based on user feedback
4. 📈 **Expand test dataset** with real production queries
5. 🚀 **Consider Phase 3** (Context & Quality improvements)

---

## Support

For issues or questions:
- Check logs: `tail -f logs/rag_evaluation.jsonl`
- Review Phase 1 docs: `PHASE1_IMPROVEMENTS.md`
- Review Phase 2 docs: `PHASE2_IMPROVEMENTS.md`
- Run diagnostics: `python test_rag_pipeline.py --limit 3`

---

**Last Updated:** 2025-11-05
**Version:** 1.0
**Applies to:** Phase 1 & 2 improvements
