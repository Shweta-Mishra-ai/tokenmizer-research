"""
Memory per token: the share of each session's labelled facts that its
TokenMizer resume block carries, at fixed token budgets (150, 250, 400).
Extraction runs incrementally, two messages at a time, as the proxy does.

    TM=/path/to/tokenmizer python -m benchmarks.memorybench.resume_budget main \
        benchmarks/corpus_heldout benchmarks/corpus_heldout2 benchmarks/corpus_heldout3

Arguments are corpus directories; "main" means the committed main corpus.
"""
import sys, os, re, tempfile, logging, statistics, collections
logging.disable(logging.CRITICAL)
from benchmarks.memorybench import corpus
from benchmarks.memorybench.metrics import covers
sys.path.insert(0, os.environ["TM"])
from tokenmizer.graph_memory.graph import GraphMemory
from tokenmizer.core.tokenizer import count_tokens
CATS = ["completed_tasks", "pending_tasks", "decisions", "files", "errors"]
def items(block):
    out = []
    for line in block.splitlines():
        body = line.split(": ", 1)[1] if ": " in line else line
        out += [p for p in re.split(r" \| |, (?=[\w./~{-])", body) if p.strip()]
    return out
res = collections.defaultdict(list); tok = collections.defaultdict(list); percat = collections.defaultdict(lambda: collections.defaultdict(list))
for cdir in sys.argv[1:]:
    for s in corpus.load(None if cdir == "main" else cdir):
        with tempfile.TemporaryDirectory() as d:
            g = GraphMemory(s.id, storage_dir=d)
            for k in range(2, len(s.messages) + 2, 2):
                g.extract_from_messages(s.messages[:k])
            for b in (150, 250, 400):
                blk = g.to_context_block(token_budget=b); its = items(blk)
                tok[b].append(count_tokens(blk))
                hit = tot = 0
                for c in CATS:
                    exp = s.expected(c)
                    h = sum(any(covers(i, e) for i in its) for e in exp)
                    hit += h; tot += len(exp)
                    if exp: percat[b][c].append(h / len(exp))
                res[b].append(hit / tot if tot else 1)
for b in (150, 250, 400):
    pc = " ".join(f"{c[:4]}={100*statistics.mean(percat[b][c]):.0f}" for c in CATS)
    print(f"budget {b}: facts carried {100*statistics.mean(res[b]):.1f}%  tokens used mean {statistics.mean(tok[b]):.0f}  | {pc}")
