"""
Download the public SWE-agent trajectories this benchmark uses.

The trajectories live in the public S3 bucket `swe-bench-submissions`
(referenced from github.com/SWE-bench/experiments, evaluation/lite/<system>/
metadata.yaml). No credentials are needed. They are not committed here:
four systems are about 400 MB of raw JSON.

    python -m benchmarks.realworld.fetch --out DATA_DIR
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


def main() -> None:
    import argparse
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--out", required=True)
    ap.add_argument("--system", action="append", choices=sorted(SYSTEMS))
    ap.add_argument("--openhands", action="store_true",
                    help="fetch the OpenHands CodeAct 2.1 trajectories and patches instead")
    args = ap.parse_args()
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
