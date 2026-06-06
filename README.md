
# TokenMizer

**Graph-Structured Session Memory for Long-Horizon LLM Context Management.**

TokenMizer is an open-source, transparent proxy system that models iterative LLM session history as a typed knowledge graph[span_1](start_span)[span_1](end_span). By extracting structured state transitions, decisions, and file modifications on the fly, it serializes long conversation histories into highly compact resume blocks—minimizing context window degradation without requiring changes to your application code[span_2](start_span)[span_2](end_span).

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://python.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.100+-green.svg)](https://fastapi.tiangolo.com)

---

## The Problem: Context Window Degradation

In iterative developer or data science sessions, interactions grow long and repetitive. At an average volume of 950 tokens per turn, a standard 16k-token Maximum Effective Context Window (MECW) is exhausted in roughly 16 turns[span_3](start_span)[span_3](end_span). 

Existing mitigations (truncation, summarization, retrieval augmentation) treat history as flat text, destroying the typed, relational structure that makes sessions resumable[span_4](start_span)[span_4](end_span).
* Architectural decisions and structural choices made early vanish[span_5](start_span)[span_5](end_span).
* Explicit task lifecycles (what is completed vs. what is pending) become blurred[span_6](start_span)[span_6](end_span).
* A natural language summary cannot reliably distinguish a completed task from a pending one, nor can it preserve the rationale for a technology decision[span_7](start_span)[span_7](end_span).

---

## The Solution: Structural State Resuming

TokenMizer intercepts raw session tokens, passes them through a deterministic compression and extraction framework, maintains a localized knowledge graph, and compresses long-horizon state into a structured **resume block** averaging **78 tokens**[span_8](start_span)[span_8](end_span).

```text
Standard Stream: [Turn 1-14 Messages (~13.3k tokens)] ──> [Context Overflow / Lost State]
TokenMizer:      [Turn 1-14 Messages] ──> Graph Extraction ──> [78-Token Resume Block Injection]

```
## System Architecture
TokenMizer operates as a transparent HTTP reverse proxy implementing the OpenAI Chat Completions API.
### 1. Knowledge Graph Schema
The structural session memory defines 14 node types across three functional categories, and 7 semantic edge types:
 * **Action Nodes (with active lifecycles):** TASK, FILE, ERROR, TEST, SCHEMA, METRIC
 * **Decision Nodes:** DECISION, DEPENDENCY, API
 * **Context Nodes (static state):** GOAL, ENVIRONMENT, PROJECT, CONCEPT, AGENT
 * **Semantic Relationships:** DEPENDS_ON, RELATED_TO, IMPLEMENTS, FIXES, BLOCKS, PART_OF, SUPERSEDES
### 2. The 8-Layer Compression Pipeline
An 8-layer compression pipeline reduces context overhead before neural stages are applied. The first 6 heuristic layers achieve 47.3% token reduction at zero inference cost.
 1. **AI Filler Removal:** Strip conversational preambles (-31.2% mean reduction).
 2. **Order-Preserving Line Deduplication:** Pruning recursive stack traces and logs (-16.1% mean reduction).
 3. **Whitespace Normalization**.
 4. **Targeted Comment Stripping**.
 5. **History Pruning**.
 6. **Smart Truncation:** Object-aware context rules.
 7. **Neural Compaction (Optional Layer 7-8):** Integrating LLMLingua-2 and LongLLMLingua.
### 3. Semantic Cache
A sentence-embedding semantic cache reduces repeated-query latency.
## Quick Start & Installation
### Automated Local Setup
For local development, use the provided setup script to enforce system prerequisites, build an isolated virtual environment, and scaffold the .env configuration. Save the following as scripts/setup.sh and execute it:
```bash
#!/usr/bin/env bash
set -euo pipefail

echo "=========================================="
echo " TokenMizer Infrastructure Setup"
echo "=========================================="

echo "--> [1/4] Checking system prerequisites..."
if ! command -v python3 &> /dev/null; then
    echo "FATAL: python3 is not installed or not in PATH." >&2
    exit 1
fi

if ! command -v docker &> /dev/null; then
    echo "FATAL: docker is not installed. Containerized vector cache cannot run." >&2
    exit 1
fi

PYTHON_VERSION=$(python3 -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')
if $(python3 -c "import sys; sys.exit(0 if sys.version_info >= (3, 10) else 1)"); then
    echo "Python version $PYTHON_VERSION detected (>= 3.10)."
else
    echo "FATAL: Python 3.10 or higher is required. Detected $PYTHON_VERSION." >&2
    exit 1
fi

echo "--> [2/4] Provisioning isolated virtual environment..."
if [ ! -d ".venv" ]; then
    python3 -m venv .venv
    echo "Created virtual environment at .venv/"
else
    echo "Virtual environment .venv/ already exists."
fi

echo "--> [3/4] Installing Python dependencies..."
source .venv/bin/activate
pip install --upgrade pip --quiet
if [ -f "pyproject.toml" ] || [ -f "setup.py" ]; then
    pip install -e ".[dev]"
elif [ -f "requirements.txt" ]; then
    pip install -r requirements.txt
else
    echo "FATAL: No dependency configuration found." >&2
    exit 1
fi

echo "--> [4/4] Configuring environment variables..."
if [ ! -f ".env" ]; then
    cat <<EOF> .env
ENVIRONMENT=development
HOST=127.0.0.1
PORT=8000
ANTHROPIC_API_KEY=sk-ant-xxx
OPENAI_API_KEY=sk-proj-xxx
ENABLE_SEMANTIC_CACHE=true
CHECKPOINT_THRESHOLD=0.85
EOF
    echo "Generated base .env file. UPDATE WITH ACTUAL API KEYS."
else
    echo ".env file already exists. Preserving local keys."
fi

echo "Setup Complete. Activate the environment with: source .venv/bin/activate"

```
### Client Integration
Point your local environment, IDE proxy, or client to the TokenMizer endpoint. Activating the workflow requires passing a tracking string (session_id) inside the request payload.
```python
from openai import OpenAI

client = OpenAI(base_url="http://localhost:8000/v1", api_key="passthrough")

response = client.chat.completions.create(
    model="claude-sonnet-4-6",
    messages=[{"role": "user", "content": "Refactor the database connection to use connection pooling."}],
    extra_body={"session_id": "production-backend-refactor"}
)

```
*Note: If no session_id is passed, the request passes through with no overhead.*
## Empirical Benchmarks
TokenMizer was evaluated on a controlled benchmark of 21 sessions spanning 5 application domains (software engineering, data science, DevOps, research/writing, and debugging). **All reported results are measured on this benchmark; no estimated values are presented**.
### Performance Profile Across Domains
Across 21 sessions and 5 domains, TokenMizer achieves mean task recall 51.0%, decision recall 46.6%, and file recall 58.7%.
| Domain | Task Recall | Decision Recall | File Recall | Mean Information Loss |
|---|---|---|---|---|
| **Software Eng (n=6)** | 47% | 70% | 72% | 37% |
| **Data Science (n=5)** | 69% | 48% | 40% | 48% |
| **DevOps (n=4)** | 45% | 38% | 50% | 56% |
| **Research (n=3)** | 44% | 44% | 33% | 59% |
| **Debugging (n=3)** | 43% | 11% | 100% | 49% |
| **Aggregate Mean** | **51.0%** | **46.6%** | **58.7%** | **48%** |
### Comparative Context Efficiency
TokenMizer produces resume blocks averaging 78 tokens (range: 42-124)—2x smaller than any evaluated baseline (159-170 tokens)—while achieving higher decision recall than all three baselines (+9-17 percentage points).
| Method | Task Recall | Decision Recall | File Recall | Mean Resume Tokens |
|---|---|---|---|---|
| Naive Truncation | 45% | 35% | 55% | 165 |
| Sliding Window (10) | 50% | 30% | 60% | 159 |
| Naive Summary | 42% | 38% | 48% | 170 |
| **TokenMizer V2** | **51%** | **47%** | **59%** | **78** |
No evaluated baseline preserves *why* a technology was chosen, only that it was mentioned.
## Current Technical Limitations
Practitioners should be aware of the architectural constraints:
 * **Synthetic Benchmark:** The benchmark is a synthetic but carefully constructed corpus. Evaluation on live developer sessions is identified as the highest-priority future work.
 * **Implicit Phrasing Vulnerability:** Sessions with implicit reasoning (research, planning) score substantially lower than sessions with explicit imperative phrasing. Several sessions exhibit 0% task recall due to highly implicit language that heuristic extraction cannot capture.
 * **Decision Recall Ceiling:** The current 47% decision recall is limited by heuristic pattern matching against indirect phrasing. A hybrid extraction pipeline with an LLM upgrade path is designed to address this.
## Research Paper Citation
If you use TokenMizer in your research, please cite:
```bibtex
@article{mishra2026tokenmizer,
  title   = {TokenMizer: Graph-Structured Session Memory for
             Long-Horizon LLM Context Management},
  author  = {Mishra, Shweta},
  journal = {arXiv preprint},
  year    = {2026},
  url     = {[https://github.com/Shweta-Mishra-ai/tokenmizer](https://github.com/Shweta-Mishra-ai/tokenmizer)}
}

```
## License
This project is distributed under the open-source **MIT License** © Shweta Mishra 2026.
```</EOF>

```
