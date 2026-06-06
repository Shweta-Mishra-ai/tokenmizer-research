 **TokenMizer**.
This version strips out the hyper-marketing fluff, drops the "Explain Like I'm 10" tone, and presents the project transparently as an architectural proxy solution. It directly reflects your actual research data, including the exact heuristic constraints, specific recall ceilings, and domain-dependent variations from your benchmark evaluations.
# TokenMizer 🧠
**Graph-Structured Session Memory for Long-Horizon LLM Context Management.**
TokenMizer is an open-source, transparent reverse proxy that models iterative LLM session history as a typed knowledge graph. By extracting structured state transitions, decisions, and file modifications on the fly, it serializes long conversation histories into highly compact context resume blocks—minimizing context window degradation without requiring changes to your application code.
License: MIT

Python 3.10+

FastAPI
## The Problem: Context Window Degradation
In iterative developer or data science sessions, interactions grow long and repetitive. At an average volume of 950 tokens per turn, a standard 16k-token Maximum Effective Context Window (MECW) is exhausted in roughly 16 turns.
When context overflows or sliding windows discard early tokens, critical session history is lost:
 * Architectural decisions and structural choices made early vanish.
 * Explicit task lifecycles (what is completed vs. what is pending) become blurred.
 * Free-text summarizations blur nuance (e.g., failing to distinguish a choice made from a choice rejected).
## The Solution: Structural State Resuming
TokenMizer intercepts raw session tokens, passes them through a deterministic compression and extraction framework, maintains a localized knowledge graph, and compresses long-horizon state into a structured **resume block** averaging **78 tokens**.
```
Standard Stream: [Turn 1-14 Messages (~13.3k tokens)] ──> [Context Overflow / Lost State]
TokenMizer:     [Turn 1-14 Messages] ──> Graph Extraction ──> [78-Token Resume Block Injection]

```
## System Architecture
TokenMizer runs locally as a containerized, lightweight HTTP proxy implementing an OpenAI-compatible Chat Completions interface.
```
Client App (Cursor/Claude Code) ──> TokenMizer Proxy ──> Upstream LLM Provider
                                         │
                    ┌────────────────────┴────────────────────┐
                    ▼                                         ▼
         [Core Processing Engine]                    [Persistent Storage]
         ├── Hybrid Graph Extractor (V2 Heuristics)   ├── SQLite Graph DB
         ├── Three-Tier Checkpoint Manager            └── JSON Checkpoint Store
         ├── 8-Layer Compression Pipeline
         └── Local Semantic Embedding Cache

```
## Quick Start
### 1. Installation & Service Start
Install the proxy package directly via pip:
```bash
pip install tokenmizer

# Set up upstream credentials and serve locally
export ANTHROPIC_API_KEY="sk-ant-..."
tokenmizer serve --host 127.0.0.1 --port 8000

```
### 2. Client Integration
Point your local environment, IDE proxy, or OpenAI/Anthropic client to the TokenMizer endpoint. Activating the workflow requires passing a tracking string (session_id) inside the request body payload.
```python
from openai import OpenAI

client = OpenAI(base_url="http://localhost:8000/v1", api_key="passthrough")

response = client.chat.completions.create(
    model="claude-sonnet-4-6",
    messages=[{"role": "user", "content": "Refactor the database connection to use connection pooling."}],
    extra_body={"session_id": "production-backend-refactor"}
)

```
*Note: If no session_id is passed, the proxy executes a zero-overhead, direct passthrough to the upstream provider.*
## Core Engine Components
### 1. Knowledge Graph Schema
The structural session memory uses an identity-addressed graph model mapping 14 distinct node classifications and 7 transactional edge types:
 * **Action Nodes (with active lifecycles):** TASK, FILE, ERROR, TEST, SCHEMA, METRIC
 * **Decision Nodes:** DECISION, DEPENDENCY, API
 * **Context Nodes (static state):** GOAL, ENVIRONMENT, PROJECT, CONCEPT, AGENT
 * **Semantic Relationships:** DEPENDS_ON, RELATED_TO, IMPLEMENTS, FIXES, BLOCKS, PART_OF, SUPERSEDES
### 2. The 8-Layer Compression Pipeline
Large raw texts (monolithic files, long API payloads, system context dumps) pass through an automated compression sequence before being indexed or contextually re-injected:
 1. **AI Filler Removal:** Strip conversational preambles and hedging patterns (-31.2% mean reduction).
 2. **Order-Preserving Line Deduplication:** Pruning recursive stack traces, logs, and duplicate code blocks (-16.1% mean reduction).
 3. **Whitespace Normalization:** Compressing blank lines and formatting tokens.
 4. **Targeted Comment Stripping:** Language-aware syntax pruning (#, //, --).
 5. **History Pruning:** Iterative validation of lengthy historical context payloads.
 6. **Smart Truncation:** Object-aware context rules (e.g., schemas + top 3 lines for data tables).
 7. **Neural Compaction (Optional Layer 7-8):** Integrating LLMLingua-2 and LongLLMLingua configurations for payloads crossing strict size thresholds.
### 3. Local Semantic Cache
Built on a localized sentence-transformer pipeline (all-MiniLM-L6-v2), the cache stores upstream responses locally. Incoming requests are vectorized and run against historical semantic vectors using cosine similarity evaluation (\theta = 0.92). Matches return instant local storage records at zero token cost and sub-millisecond latencies.
## Controlled Empirical Benchmarks
The framework was evaluated across a controlled, static corpus of 21 synthetic session logs mapping common development contexts.
### Performance Profile Across Domains
Evaluation demonstrates high architectural performance in structured command environments, alongside a clear performance drop-off when analyzing natural, implicit language (e.g., planning, high-level research summaries):
| Domain Split | Task Recall | Decision Recall | File Recall | Mean Information Loss |
|---|---|---|---|---|
| **Software Engineering (n=6)** | 47% | 70% | 72% | 37% |
| **Data Science (n=5)** | 69% | 48% | 40% | 48% |
| **DevOps (n=4)** | 45% | 38% | 50% | 56% |
| **Research/Writing (n=3)** | 44% | 44% | 33% | 59% |
| **Debugging (n=3)** | 43% | 11% | 100% | 49% |
| **Aggregate Dataset Mean** | **51%** | **47%** | **59%** | **48%** |
### Comparative Context Efficiency
Baselines were tracked by matching textual entities against historical boundaries using identical fuzzy label parameters:
| Metric Backing | Task Recall | Decision Recall | File Recall | Mean Resume Token Footprint |
|---|---|---|---|---|
| Naive Truncation (Last 300 tokens) | 45% | 35% | 55% | 165 tokens |
| Sliding Window (Last 10 messages) | 50% | 30% | **60%** | 159 tokens |
| Naive Summary (Concatenated blocks) | 42% | 38% | 48% | 170 tokens |
| **TokenMizer V2 Engine** | **51%** | **47%** | 59% | **78 tokens** |
## Current Technical Limitations
Practitioners integrating TokenMizer into highly specific developer workflows should be aware of the current architectural parameters:
 * **Heuristic Dependency:** The V2 default processing engine relies on deterministic compiled regex layers. Implicit conversational assertions (e.g., *"Let's tentatively roll out Redis and see how it performs"*) escape traditional trigger matching, contributing to the current 47% decision recall ceiling.
 * **Overfitting Risks:** The default extraction models are optimized around concrete, action-oriented syntax patterns. Conversations relying on highly implicit or academic prose (e.g., the grant_proposal_nsf evaluation set) inherently trigger poor or zero-recall structural matching profiles.
 * **Evaluation Scope:** Current benchmark statistics are derived entirely from structured, synthetic developer sessions engineered by the repository maintainer. Production evaluation on dynamic, live developer histories represents active, unquantified work.
## Data Privacy & Security Guardrails
TokenMizer is designed for air-gapped security compliance:
 * **Zero Telemetry Leakage:** The graph extraction layer, regex processors, caching databases, and embedding functions execute completely in-memory or within localized persistent SQLite layers. No payloads are transferred over public monitoring networks.
 * **Credential Redaction:** Input tokens are parsed through pre-extraction sanitization filters targeting API tokens, cryptography blocks, and environment passwords, masking matches immediately to [REDACTED].
## Development & Test Automation
Run tests inside a isolated virtual environment using the local development suite:
```bash
# Clone and enter directory
git clone https://github.com/Shweta-Mishra-ai/tokenmizer.git
cd tokenmizer

# Editable developer install
pip install -e ".[dev]"

# Execute full testing pipeline (unit, integration, and structural mutations)
pytest tests/ -v --cov=tokenmizer

```
## License
This architecture is distributed under the open-source **MIT License** © Shweta Mishra 2026.
