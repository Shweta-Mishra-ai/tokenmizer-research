"""
Download the public SWE-agent trajectories this benchmark uses.

The trajectories live in the public S3 bucket `swe-bench-submissions`
(referenced from github.com/SWE-bench/experiments, evaluation/lite/<system>/
metadata.yaml). No credentials are needed. They are not committed here:
four systems are about 400 MB of raw JSON.

    python -m benchmarks.realworld.fetch --out DATA_DIR

As of 2026-11-12 the bucket refuses LISTING (S3 AccessDenied) while every
object still downloads. The listing step above therefore fails; fetch the
sessions a committed result file names instead, by their known keys:

    python -m benchmarks.realworld.fetch --out DATA_DIR \
        --sessions-from benchmarks/results/realworld/test_fix.json

That file names all 716 test-split sessions (five systems). Then convert
them as before (swe_trajectories / openhands_trajectories).
"""
from __future__ import annotations

import re
import subprocess
import urllib.parse
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

BUCKET = "https://swe-bench-submissions.s3.amazonaws.com/"
SYSTEMS = {
    "sweagent_gpt4": "lite/20240402_sweagent_gpt4/trajs/",
    "sweagent_claude3opus": "lite/20240402_sweagent_claude3opus/trajs/",
    "sweagent_claude35sonnet": "lite/20240620_sweagent_claude3.5sonnet/trajs/",
    "sweagent_gpt4o": "lite/20240728_sweagent_gpt4o/trajs/",
}


def _curl(url: str, out: Path | None = None) -> str:
    cmd = ["curl", "-sS", "--fail", "--max-time", "180", url]
    if out is not None:
        cmd += ["-o", str(out)]
    return subprocess.run(cmd, capture_output=True, text=True, check=True).stdout


def list_keys(prefix: str) -> list[str]:
    keys: list[str] = []
    token = None
    while True:
        url = f"{BUCKET}?list-type=2&prefix={urllib.parse.quote(prefix)}"
        if token:
            url += "&continuation-token=" + urllib.parse.quote(token)
        body = _curl(url)
        keys += [k for k in re.findall(r"<Key>([^<]+)</Key>", body) if k.endswith(".traj")]
        m = re.search(r"<NextContinuationToken>([^<]+)</NextContinuationToken>", body)
        if not m:
            return keys
        token = m.group(1)


OPENHANDS = "lite/20241025_OpenHands-CodeAct-2.1-sonnet-20241022/"


def fetch_openhands(out: Path) -> None:
    """OpenHands stores each trajectory as trajs/<instance>.json and the
    submitted patch in the evaluation logs as logs/<instance>/patch.diff."""
    dest = out / "openhands_codeact21"
    (dest / "patches").mkdir(parents=True, exist_ok=True)
    keys: list[str] = []
    token = None
    while True:
        url = f"{BUCKET}?list-type=2&prefix={urllib.parse.quote(OPENHANDS + 'trajs/')}"
        if token:
            url += "&continuation-token=" + urllib.parse.quote(token)
        body = _curl(url)
        keys += [k for k in re.findall(r"<Key>([^<]+)</Key>", body) if k.endswith(".json")]
        m = re.search(r"<NextContinuationToken>([^<]+)</NextContinuationToken>", body)
        if not m:
            break
        token = m.group(1)

    def one(key: str) -> None:
        inst = Path(key).stem
        if not (dest / f"{inst}.json").exists():
            _curl(BUCKET + urllib.parse.quote(key), dest / f"{inst}.json")
        if not (dest / "patches" / f"{inst}.diff").exists():
            try:
                _curl(BUCKET + urllib.parse.quote(f"{OPENHANDS}logs/{inst}/patch.diff"),
                      dest / "patches" / f"{inst}.diff")
            except subprocess.CalledProcessError:
                pass   # no evaluation log: the instance has no submitted patch
    with ThreadPoolExecutor(8) as pool:
        list(pool.map(one, keys))
    print(f"openhands_codeact21: {len(keys)} trajectories in {dest}")


def fetch_sessions(out: Path, results_json: Path) -> None:
    """Download the trajectories a run_real result file names, by key.

    Needs no bucket listing: a session id is `<system>__<instance>`, and
    each system's objects sit at a known prefix.
    """
    import json

    data = json.loads(results_json.read_text())
    ids = sorted({r["session_id"] for rows in data["rows"].values() for r in rows})

    def one(sid: str) -> bool:
        system, instance = sid.split("__", 1)
        if system == "openhands_codeact21":
            dest = out / system
            (dest / "patches").mkdir(parents=True, exist_ok=True)
            pairs = [(f"{OPENHANDS}trajs/{instance}.json", dest / f"{instance}.json"),
                     (f"{OPENHANDS}logs/{instance}/patch.diff",
                      dest / "patches" / f"{instance}.diff")]
        else:
            dest = out / system
            dest.mkdir(parents=True, exist_ok=True)
            pairs = [(f"{SYSTEMS[system]}{instance}.traj", dest / f"{instance}.traj")]
        ok = True
        for key, path in pairs:
            if path.exists():
                continue
            try:
                _curl(BUCKET + urllib.parse.quote(key), path)
            except subprocess.CalledProcessError:
                ok = ok and key.endswith("patch.diff")   # a patch can be absent
        return ok

    with ThreadPoolExecutor(8) as pool:
        got = sum(pool.map(one, ids))
    print(f"{got} of {len(ids)} sessions in {out}")


def main() -> None:
    import argparse
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--out", required=True)
    ap.add_argument("--system", action="append", choices=sorted(SYSTEMS))
    ap.add_argument("--openhands", action="store_true",
                    help="fetch the OpenHands CodeAct 2.1 trajectories and patches instead")
    ap.add_argument("--sessions-from", type=Path,
                    help="fetch exactly the sessions this run_real result JSON names, "
                         "without listing the bucket")
    args = ap.parse_args()
    if args.sessions_from:
        fetch_sessions(Path(args.out), args.sessions_from)
        return
    if args.openhands:
        fetch_openhands(Path(args.out))
        return
    for name in args.system or sorted(SYSTEMS):
        dest = Path(args.out) / name
        dest.mkdir(parents=True, exist_ok=True)
        keys = list_keys(SYSTEMS[name])
        todo = [k for k in keys if not (dest / Path(k).name).exists()]
        with ThreadPoolExecutor(8) as pool:
            list(pool.map(lambda k: _curl(BUCKET + urllib.parse.quote(k), dest / Path(k).name), todo))
        print(f"{name}: {len(keys)} trajectories in {dest}")


if __name__ == "__main__":
    main()
