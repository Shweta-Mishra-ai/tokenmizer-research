"""
Graph relations formed when a session is extracted all at once, against
one message at a time (the way the proxy extracts). Reports how many of
the all-at-once edges incremental extraction also forms.

    TM=/path/to/tokenmizer python -m benchmarks.memorybench.graph_edges main \
        benchmarks/corpus_heldout benchmarks/corpus_heldout2 benchmarks/corpus_heldout3
"""
import sys, os, tempfile, logging, collections, glob, json
logging.disable(logging.CRITICAL)
from benchmarks.memorybench import corpus
sys.path.insert(0, os.environ["TM"])
from tokenmizer.graph_memory.graph import GraphMemory
def edges(g):
    lab = {n.id: (n.type.value, n.label.lower()) for n in g._nodes.values()}
    return {(e.type.value, lab.get(e.source_id), lab.get(e.target_id)) for e in g._edges
            if e.source_id in lab and e.target_id in lab}
tot_batch = tot_inc = common = 0; by = collections.Counter(); byi = collections.Counter()
sessions = []
for cdir in sys.argv[1:]:
    sessions += [s.messages for s in corpus.load(None if cdir == "main" else cdir)]
for msgs in sessions:
    with tempfile.TemporaryDirectory() as d1, tempfile.TemporaryDirectory() as d2:
        a = GraphMemory("a", storage_dir=d1); a.extract_from_messages(msgs, incremental=False)
        b = GraphMemory("b", storage_dir=d2)
        for k in range(1, len(msgs) + 1): b.extract_from_messages(msgs[:k])
        ea, eb = edges(a), edges(b)
        tot_batch += len(ea); tot_inc += len(eb); common += len(ea & eb)
        for t, _, _ in ea: by[t] += 1
        for t, _, _ in eb: byi[t] += 1
print(f"sessions {len(sessions)}  edges all-at-once {tot_batch}  incremental {tot_inc}  shared {common}")
for t in sorted(set(by) | set(byi)): print(f"   {t:14} all-at-once {by[t]:5}  incremental {byi[t]:5}")
