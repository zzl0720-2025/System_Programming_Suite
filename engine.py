"""Shared experiment dispatch, memory inputs, and trace files."""

import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parent
BINARY = ROOT / "build" / "memory-engine"
POLICIES = ("fifo", "random", "clock", "nru", "aging", "working-set")
CONFIG_KEYS = ("schema_version", "module", "algorithm", "frames", "references",
               "writes", "seed", "reset_interval", "window")
POLICY_NOTES = {
    "fifo": "Replace the resident page loaded earliest. Hits do not change load order.",
    "random": "Choose MT19937(seed) modulo frame count. Draw only when a full memory needs replacement.",
    "clock": "Clear reference bits while scanning from the hand; replace the first unmarked page.",
    "nru": "Choose the lowest (referenced, dirty) class: 00, 01, 10, 11. Reset reference bits periodically.",
    "aging": "Periodically shift 32-bit counters right and insert the reference bit at bit 31. Choose the smallest counter.",
    "working-set": "Scan from the hand. Refresh marked pages' timestamps; evict an unmarked page older than the window, or the oldest sampled page.",
}


def build():
    sources = sorted((ROOT / "core").glob("*.cpp"))
    dependencies = sources + sorted((ROOT / "core").glob("*.hpp"))
    if BINARY.exists() and BINARY.stat().st_mtime >= max(p.stat().st_mtime for p in dependencies):
        return
    compiler = shutil.which(os.environ.get("CXX", "c++"))
    if not compiler:
        raise ValueError("A C++17 compiler is required. Set CXX to its executable name.")
    BINARY.parent.mkdir(exist_ok=True)
    handle, temporary = tempfile.mkstemp(prefix="memory-", dir=BINARY.parent)
    os.close(handle)
    try:
        subprocess.run([compiler, "-std=c++17", "-O2", "-Wall", "-Wextra", "-pedantic",
                        *map(str, sources), "-o", temporary], check=True)
        # Readers see a complete executable, including when two commands build at once.
        os.replace(temporary, BINARY)
    finally:
        Path(temporary).unlink(missing_ok=True)


def integer(value, name, low, high):
    if type(value) is not int or not low <= value <= high:
        raise ValueError(f"{name} must be an integer between {low} and {high}.")
    return value


def validate(config):
    if not isinstance(config, dict):
        raise ValueError("An experiment must be a JSON object.")
    if config.get("module") != "memory":
        from module_api import validate as validate_module
        return validate_module(config)
    unknown = config.keys() - set(CONFIG_KEYS)
    if unknown:
        raise ValueError(f"Unknown configuration fields: {', '.join(sorted(unknown))}.")
    integer(config.get("schema_version"), "schema_version", 1, 1)
    if config.get("algorithm") not in POLICIES:
        raise ValueError(f"Choose a policy: {', '.join(POLICIES)}.")
    frames = integer(config.get("frames"), "Frame count", 1, 64)
    references = config.get("references")
    if not isinstance(references, list) or not 1 <= len(references) <= 4096:
        raise ValueError("Provide between 1 and 4096 page references.")
    for page in references:
        integer(page, "Page number", 0, 999)
    writes = config.get("writes", [])
    if not isinstance(writes, list):
        raise ValueError("writes must be a list of zero-based access indices.")
    for index in writes:
        integer(index, "Write index", 0, len(references) - 1)
    if len(set(writes)) != len(writes):
        raise ValueError("Write indices must not repeat.")
    return {
        "schema_version": 1, "module": "memory", "algorithm": config["algorithm"],
        "frames": frames, "references": list(references), "writes": sorted(writes),
        "seed": integer(config.get("seed", 1), "Seed", 0, 2**32 - 1),
        "reset_interval": integer(config.get("reset_interval", 4), "Reset interval", 1, 4096),
        "window": integer(config.get("window", 4), "Working-set window", 1, 4096),
    }


def run(config):
    config = validate(config)
    if config["module"] != "memory":
        from module_api import run as run_module
        return run_module(config)
    writes = set(config["writes"])
    tokens = [("w" if index in writes else "r") + str(page)
              for index, page in enumerate(config["references"])]
    process = subprocess.run([
        str(BINARY), config["algorithm"], str(config["frames"]),
        "--seed", str(config["seed"]), "--reset", str(config["reset_interval"]),
        "--window", str(config["window"]), *tokens,
    ], capture_output=True, text=True, timeout=15)
    if process.returncode:
        raise ValueError(process.stderr.strip() or "The memory engine failed.")
    return json.loads(process.stdout)


def compare(config, algorithms=None, frame_counts=None):
    config = validate(config)
    if config["module"] != "memory":
        from module_api import compare as compare_module
        return compare_module(config,algorithms,frame_counts)
    algorithms = POLICIES if algorithms is None else algorithms
    algorithms = tuple(algorithms)
    if not algorithms or any(name not in POLICIES for name in algorithms):
        raise ValueError(f"Choose policies from: {', '.join(POLICIES)}.")
    frame_counts = list(frame_counts) if frame_counts is not None else [config["frames"]]
    if not frame_counts or len(frame_counts) > 64:
        raise ValueError("Provide between 1 and 64 frame counts.")
    for frames in frame_counts:
        integer(frames, "Frame count", 1, 64)
    rows = []
    for frames in frame_counts:
        for algorithm in algorithms:
            result = run({**config, "algorithm": algorithm, "frames": frames})
            rows.append({"algorithm": algorithm, "frames": frames, "seed": config["seed"],
                         **result["summary"],
                         "hit_rate": result["summary"]["hits"] / len(config["references"])})
    return rows


def read_json(path):
    path = Path(path)
    if path.stat().st_size > 128 * 1024 * 1024:
        raise ValueError("Choose a JSON file smaller than 128 MB.")
    return json.loads(path.read_text(encoding="utf-8"))


def load_config(path):
    return validate(read_json(path))


def verify_trace(path):
    trace = read_json(path)
    if not isinstance(trace, dict) or "events" not in trace:
        raise ValueError("Expected an exported trace, including its event list.")
    config = validate(trace["config"] if "config" in trace else {key: trace[key] for key in CONFIG_KEYS if key in trace})
    if run(config) != trace:
        raise ValueError("The saved trace does not match this engine. Re-run its configuration.")
    return trace


def write_file(path, content, force=False):
    with Path(path).open("w" if force else "x", encoding="utf-8", newline="") as stream:
        stream.write(content)


def parse_references(text):
    tokens = text.replace(",", " ").split()
    references, writes = [], []
    for index, token in enumerate(tokens):
        prefix = token[:1].lower()
        number = token[1:] if prefix in ("r", "w") else token
        if not number.isascii() or not number.isdecimal():
            raise ValueError(f"Invalid reference {token!r}. Use 7, r7, or w7.")
        references.append(int(number))
        if prefix == "w":
            writes.append(index)
    if not references:
        raise ValueError("Provide at least one page reference.")
    return references, writes
