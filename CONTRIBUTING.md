# Contributing to TokenMizer

Thank you for your interest! Here are the highest-priority areas:

## Priority Contributions

1. **Real-session evaluation data** — Annotated developer sessions (any domain)
2. **LLM extractor evaluation** — Measure recall with Claude Haiku / GPT-4o-mini
3. **More benchmark sessions** — Additional domains (mobile, embedded, ML ops)
4. **Embedding-based edge linking** — sentence-transformers already a dependency
5. **Cross-session memory** — SQLite backend already supports it architecturally

## Adding a Benchmark Session

Add to `benchmarks/checkpoint_accuracy/runner_v2.py`, `SESSIONS` dict:

```python
"your_session_name": {
    "domain": "software_engineering",  # or data_science, devops, research, debugging
    "messages": [
        {"role": "user", "content": "..."},
        {"role": "assistant", "content": "Completed: ... Decided: ..."},
        ...
    ],
    "ground_truth": {
        "completed_tasks": ["task1", "task2"],
        "pending_tasks": ["task3"],
        "decisions": ["technology choice"],
        "files": ["path/to/file.py"],
    },
}
```

## Setup

```bash
git clone https://github.com/Shweta-Mishra-ai/tokenmizer
cd tokenmizer
pip install -e ".[dev]"
```
