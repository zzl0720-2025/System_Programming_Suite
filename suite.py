#!/usr/bin/env python3
"""Systems Programming Suite: local experiments, interactive shell, and web workspace."""

import argparse
import json
import re
import shutil
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import subprocess
import sys
from urllib.parse import urlsplit

from engine import (BINARY, ROOT, CONFIG_KEYS, POLICIES, POLICY_NOTES, build, compare, load_config,
                    parse_references, run, validate, verify_trace, write_file)
from reports import format_result
from session import MemorySession
from experiment_session import ExperimentSession
import module_api
import compiler_driver

EXAMPLES = {"memory": "first-pages", **{name: name for name in module_api.ALGORITHMS}}


class Handler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(ROOT / "web"), **kwargs)

    def end_headers(self):
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Cache-Control", "no-store")
        super().end_headers()

    def reply(self, status, value):
        data = json.dumps(value).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        path = urlsplit(self.path).path
        if path == "/api/health":
            self.reply(200, {"status": "ready", "modules": list(EXAMPLES), "policies": POLICIES,
                              "ocaml": bool(shutil.which("ocamlc")), "qemu": bool(shutil.which("qemu-system-riscv64"))})
        elif path == "/api/examples":
            self.reply(200, {name: load_config(ROOT / "examples" / f"{filename}.json")
                             for name, filename in EXAMPLES.items()})
        elif re.fullmatch(r"/api/artifacts/[a-f0-9]{24}/program\.(s|elf)", path):
            artifact = ROOT / "build" / "artifacts" / Path(path).parent.name / Path(path).name
            if not artifact.is_file():
                self.reply(404, {"error": "Run the compiler first to create this artifact."})
                return
            data = artifact.read_bytes()
            self.send_response(200)
            self.send_header("Content-Type", "application/octet-stream")
            self.send_header("Content-Disposition", f'attachment; filename="{artifact.name}"')
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)
        elif path == "/api/policies":
            self.reply(200, {"policies": POLICY_NOTES})
        else:
            super().do_GET()

    def do_POST(self):
        if self.path not in ("/api/run", "/api/compare"):
            self.reply(404, {"error": "Unknown endpoint."})
            return
        try:
            if self.headers.get_content_type() != "application/json":
                raise ValueError("Send the experiment as application/json.")
            size = int(self.headers.get("Content-Length", "0"))
            if not 0 < size <= 262144:
                raise ValueError("Request body must be between 1 and 262144 bytes.")
            config = json.loads(self.rfile.read(size))
            self.reply(200, run(config) if self.path == "/api/run" else compare(config))
        except (ValueError, UnicodeError) as error:
            self.reply(400, {"error": str(error)})
        except (OSError, subprocess.SubprocessError):
            self.reply(500, {"error": "The experiment could not run. Check the server terminal."})


def output_arguments(parser):
    parser.add_argument("--format", choices=("json", "table", "csv"), default="json")
    parser.add_argument("--output", type=Path, help="Write to this file instead of stdout")
    parser.add_argument("--force", action="store_true", help="Allow overwriting --output")


def experiment_arguments(parser):
    parser.add_argument("experiment", type=Path, nargs="?", default=None)
    parser.add_argument("--module", choices=EXAMPLES)
    parser.add_argument("--policy")
    parser.add_argument("--quantum", type=int)
    parser.add_argument("--head", type=int)
    parser.add_argument("--page-size", type=int)
    parser.add_argument("--source-file", type=Path)
    parser.add_argument("--no-verify", action="store_true")
    parser.add_argument("--frames", type=int)
    parser.add_argument("--seed", type=int)
    parser.add_argument("--reset-interval", type=int)
    parser.add_argument("--window", type=int)
    parser.add_argument("--references", help='Access sequence, for example "1 r2 w3 1"')


def configuration(args):
    config = load_config(args.experiment or ROOT / "examples" / f"{EXAMPLES[args.module or 'memory']}.json")
    if args.module and config["module"] != args.module:
        raise ValueError("The selected module does not match the experiment file.")
    for flag, key in (("policy", "algorithm"), ("frames", "frames"), ("seed", "seed"),
                      ("reset_interval", "reset_interval"), ("window", "window"),
                      ("quantum", "quantum"), ("head", "head"), ("page_size", "page_size")):
        value = getattr(args, flag, None)
        if value is not None:
            config[key] = value
    if args.source_file:
        if config["module"] != "compiler": raise ValueError("--source-file requires the compiler module.")
        config["source"] = args.source_file.read_text()
    if args.no_verify:
        if config["module"] != "compiler": raise ValueError("--no-verify requires the compiler module.")
        config["verify"] = False
    if args.references is not None:
        if config["module"] != "memory": raise ValueError("--references requires the memory module.")
        config["references"], config["writes"] = parse_references(args.references)
    return validate(config)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("build", help="Build the C++ engines and OCaml compiler")
    commands.add_parser("list", help="List implemented modules and policies")
    for name in ("run", "compare", "shell"):
        command = commands.add_parser(name, help={
            "run": "Run an experiment and output a trace",
            "compare": "Compare policies or frame counts on one workload",
            "shell": "Start an interactive experiment session",
        }[name])
        experiment_arguments(command)
        if name != "shell":
            output_arguments(command)
        if name == "compare":
            command.add_argument("--algorithms", nargs="+", default=None)
            command.add_argument("--frame-counts", type=int, nargs="+")
    replay = commands.add_parser("replay", help="Verify an exported trace and inspect it interactively")
    replay.add_argument("trace", type=Path)
    serve = commands.add_parser("serve", help="Start the local web workspace")
    serve.add_argument("--port", type=int, default=8765)
    args = parser.parse_args()
    if args.command == "list":
        print("memory       Single-process page replacement: " + ", ".join(POLICIES))
        for name, algorithms in module_api.ALGORITHMS.items():
            print(f"{name:12} " + (", ".join(algorithms) or {
                "linker": "Two-pass symbol resolution and relocation: I, A, R, E, M",
                "compiler": "OCaml front end, reference interpreter, RV64IM ELF, QEMU verification"
            }.get(name, "")))
        print("\nAll modules support run, shell, trace exports, and the web workspace.\n"
              "vm adds process page tables, address translation, protection, swap, and exit handling.")
        return 0
    build()
    module_api.build_native()
    if args.command == "build":
        compiler_driver.build()
        print("C++ engines and OCaml compiler are ready.")
    elif args.command in ("run", "compare"):
        config = configuration(args)
        result = (run(config) if args.command == "run" else
                  compare(config, args.algorithms, args.frame_counts))
        content = format_result(result, args.format, comparison=args.command == "compare")
        if args.output:
            write_file(args.output, content, args.force)
        else:
            print(content, end="")
    elif args.command in ("shell", "replay"):
        if args.command == "replay":
            trace = verify_trace(args.trace)
            config = trace.get("config") or {key: trace[key] for key in CONFIG_KEYS}
        else:
            config = configuration(args)
        interactive = sys.stdin.isatty()
        session_class = MemorySession if config["module"] == "memory" else ExperimentSession
        session = session_class(config, stdin=None if interactive else sys.stdin)
        session.do_state("")
        while True:
            try:
                session.cmdloop()
                break
            except KeyboardInterrupt:
                print("\nCommand interrupted. The current experiment is still available.")
                session.intro = None
        return int(session.errors > 0) if not interactive else 0
    else:
        with ThreadingHTTPServer(("127.0.0.1", args.port), Handler) as server:
            print(f"Systems Programming Suite: http://127.0.0.1:{args.port}", flush=True)
            try:
                server.serve_forever()
            except KeyboardInterrupt:
                pass
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except (ValueError, OSError, subprocess.SubprocessError) as error:
        print(f"Error: {error}", file=sys.stderr)
        sys.exit(2)
