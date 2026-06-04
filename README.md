# TokenMizer 🧠

**Graph-structured session memory for efficient LLM context preservation.**

TokenMizer is an open-source, transparent proxy that models LLM session history as a typed knowledge graph — preventing context loss in long-horizon sessions without changing a single line of your application code.

[![arXiv](https://img.shields.io/badge/arXiv-2026-red)](https://arxiv.org)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://python.org)

---

## The Problem

At ~950 tokens/turn, a development session exhausts a 16k-token context window after just 16 turns. When that happens:
- Architectural decisions made in turn 3 vanish
- Technology choices and their rationales are lost
- Completed vs pending task status disappears

Existing mitigations (truncation, summarization) treat history as **flat text** — they can't distinguish a *completed* task from a *pending* one, or record *why* Redis was chosen over PostgreSQL.

## The Solution

TokenMizer extracts **structured session state** into a typed knowledge graph (14 node types, 7 edge types), then serializes it into a compact **resume block** averaging **78 tokens** — 2× smaller than any text-retention baseline, while achieving higher decision recall.

```
Without TokenMizer: turn 16 → context overflow → session lost
With TokenMizer:    turn 14 → checkpoint (78 tok) → session continues indefinitely
```

---

## Quick Start

```bash
pip install tokenmizer

# Start the proxy (configure your LLM provider API key first)
export ANTHROPIC_API_KEY=sk-ant-...
tokenmizer serve
```

Then point your OpenAI-compatible client to `http://localhost:8000`:

```python
from openai import OpenAI

client = OpenAI(base_url="http://localhost:8000/v1", api_key="any")

response = client.chat.completions.create(
    model="claude-sonnet-4-6",
    messages=[{"role": "user", "content": "Build a FastAPI auth service"}],
    extra_body={"session_id": "my-project"}  # activates full pipeline
)
```

No `session_id`? Zero overhead — requests pass through unchanged.

---

## How It Works

```
Client App  →  TokenMizer Proxy  →  LLM Provider
               ┌─────────────────────────────────┐
               │  Graph Memory     (14 node types)│
               │  Hybrid Extractor (heuristic+LLM)│
               │  Checkpoint Mgr   (3 tiers)      │
               │  Compression      (8 layers)     │
               │  Semantic Cache   (embeddings)   │
               └─────────────────────────────────┘
               SQLite Graph DB    Checkpoint Store
```

### Graph Schema
| Node Category | Types |
|---------------|-------|
| Action nodes  | TASK, FILE, ERROR, TEST, SCHEMA, METRIC |
| Decision nodes| DECISION, DEPENDENCY, API |
| Context nodes | GOAL, ENVIRONMENT, PROJECT, CONCEPT, AGENT |

Edge types: `DEPENDS_ON`, `RELATED_TO`, `IMPLEMENTS`, `FIXES`, `BLOCKS`, `PART_OF`, `SUPERSEDES`

### Checkpoint Tiers
| Tier | Content | Token Budget |
|------|---------|--------------|
| Critical | GOAL + in-progress tasks + top decision | ≤ 100 |
| Standard | All tasks + decisions + files + env | ≤ 300 |
| Full | Complete graph | ≤ 600 |

### Compression Pipeline (zero external deps for layers 1–6)
1. Filler removal — **31.2% reduction**
2. Deduplication — **16.1% reduction**
3. Whitespace normalization
4. Comment stripping
5. History pruning
6. File-type smart truncation
7. LLMLingua-2 (optional)
8. LongLLMLingua (optional)

**Total heuristic reduction: 47.3%**

---

## Benchmark Results

Evaluated on 21 sessions across 5 domains (software engineering, data science, DevOps, research, debugging):

| Method | Task Recall | Decision Recall | File Recall | Avg Tokens |
|--------|-------------|-----------------|-------------|------------|
| Naive Truncation | 45% | 35% | 55% | 165 |
| Sliding Window | 50% | 30% | 60% | 159 |
| Naive Summary | 42% | 38% | 48% | 170 |
| **TokenMizer V2** | **51%** | **47%** | 59% | **78** |

Key: **2× fewer tokens, highest decision recall.** No baseline preserves *why* decisions were made.

See [`benchmarks/`](benchmarks/) to reproduce all results.

---

## Supported Providers

| Provider | Models | Free tier |
|----------|--------|-----------|
| Anthropic | Claude 3/4 family | No |
| OpenAI | GPT-4o, o-series | No |
| Google | Gemini 1.5/2.0 | Yes |
| Groq | Llama 3.x | Yes |
| OpenRouter | 100+ models | Partial |
| DeepSeek | DeepSeek-V3 | Partial |
| Mistral | Mistral/Mixtral | No |
| Cohere | Command R+ | No |
| Ollama | Any local model | Yes |

---

## Configuration

```yaml
# tokenmizer.yaml
provider: anthropic
default_model: claude-sonnet-4-6

graph_checkpoint:
  enabled: true
  trigger_at_percent: 0.85
  use_llm_extraction: false  # set true for better recall, adds cost
  max_nodes: 500

compression:
  enabled: true
  engine: heuristic
  min_tokens_to_compress: 300

cache:
  enabled: true
  similarity_threshold: 0.92
  ttl_seconds: 3600

validator:
  min_confidence: 0.50
```

---

## Research Paper

**TokenMizer: Graph-Structured Session Memory for Long-Horizon LLM Context Management**
Shweta Mishra, Independent Researcher, 2026.

→ [arXiv preprint](#) *(link after submission)*

If you use TokenMizer in your research, please cite:
```bibtex
@article{mishra2026tokenmizer,
  title   = {TokenMizer: Graph-Structured Session Memory for
             Long-Horizon LLM Context Management},
  author  = {Mishra, Shweta},
  journal = {arXiv preprint},
  year    = {2026},
  url     = {https://github.com/Shweta-Mishra-ai/tokenmizer}
}
```

---

## Contributing

Contributions welcome! Priority areas:
- Real-session evaluation data
- LLM extractor evaluation
- Embedding-based edge linking
- Cross-session memory

See [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines.

---

## License

MIT © Shweta Mishra 2026
