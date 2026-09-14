# Systems Programming Suite

An open-source platform for learning systems programming and experimenting with memory management, scheduling, linking, and compilation. Beginners can follow guided lessons in a browser; experienced users can configure workloads, compare algorithms, and inspect reproducible traces through the browser or command line.

## Why this project exists

Systems concepts become easier to understand when you can watch a mechanism make a decision. A page table diagram explains a mapping, but stepping through two processes using the same virtual address shows why that mapping matters. A scheduling rule becomes more concrete when you change an arrival time and see which process runs next.

This project gives newcomers a place to build that understanding through small examples: learn a concept, predict the next event, observe the result, and change an input. Each lesson explains the terms it uses and connects them to a working simulation.

For users who already know the concepts, the same engines provide a simulator platform for controlled experiments. Supply your own workloads, compare policies under identical conditions, inspect individual decisions, and export results for further analysis. The browser and CLI use the same backend traces, so an experiment explored visually can also be reproduced in a terminal or script.

## Choose your workflow

| What you want to do | Start here |
| --- | --- |
| Learn the concepts with explanations and visual examples | [Browser: Learn](#browser-learn) |
| Edit inputs and explore algorithm behavior visually | [Browser: Lab](#browser-lab) |
| Work directly with configurations and inspect state interactively | [Interactive command line](#interactive-command-line) |
| Run comparisons, export data, or automate experiments | [Batch experiments](#batch-experiments) |

## What you can explore

| Browser workspace | CLI module | Implementation and experiments |
| --- | --- | --- |
| Virtual memory | `memory` | C++ page replacement: FIFO, Random, Clock, NRU, Aging, Working Set; hits, faults, and dirty evictions |
| Address spaces | `vm` | C++ multi-process virtual memory: separate page tables, byte-address translation, protection, swap, file-backed pages, and process exit |
| CPU scheduling | `cpu` | C++ scheduling: FCFS, LCFS, SRTF, RR, PRIO, PREPRIO; CPU/I/O bursts, preemption, waiting, and response |
| Disk scheduling | `disk` | C++ scheduling: FIFO, SSTF, LOOK, CLOOK, FLOOK; head movement, request arrivals, and waiting |
| Linking | `linker` | C++ two-pass linker: symbol definitions, forward references, I/A/R/E/M relocation, and diagnostics |
| Compilation | `compiler` | OCaml front end and code generator: tokens, syntax trees, semantic checks, reference evaluation, RV64IM assembly and ELF, and QEMU execution |

The two memory workspaces separate introductory page replacement from process address translation. Every module is available immediately. Learning progress never blocks access to another module.

## Setup

Download the repository and open a terminal in the directory containing `suite.py`, `core/`, and `web/`. All commands below run from that directory. If your download contains a `systems-suite/` subdirectory, enter it first.

### Requirements

| Component | Needed for |
| --- | --- |
| Python 3.9+ and a C++17 compiler available as `c++` | Browser server, CLI, memory, CPU, disk, and linker engines |
| OCaml with `ocamlc` on `PATH` | The compilation module and the full `build` command |
| `qemu-system-riscv64` on `PATH` | Executing generated RISC-V programs and checking their results |
| A modern browser with JavaScript enabled | The Learn and Lab interface |

There are no Python or JavaScript packages to install. The CLI runs directly without a browser or web server. Set `CXX` if your C++ compiler uses another executable name, for example `CXX=g++ python3 suite.py serve`.

### macOS

If you do not already have a C++ compiler, install Apple's Command Line Tools and finish the installer before continuing:

```sh
xcode-select --install
```

With [Homebrew](https://brew.sh/) installed, install Python if needed:

```sh
brew install python
```

To use the complete compiler pipeline, also install [OCaml](https://formulae.brew.sh/formula/ocaml) and [QEMU](https://formulae.brew.sh/formula/qemu):

```sh
brew install ocaml qemu
```

### Debian / Ubuntu

Install the base tools:

```sh
sudo apt update
sudo apt install python3 g++
```

For compilation, also install OCaml:

```sh
sudo apt install ocaml
```

Install the package that provides RISC-V system emulation for your distribution. On [Debian 13](https://packages.debian.org/en/trixie/qemu-system-riscv):

```sh
sudo apt install qemu-system-riscv
```

On [Ubuntu 24.04](https://packages.ubuntu.com/noble/qemu-system-misc):

```sh
sudo apt install qemu-system-misc
```

The recorded project validation was performed on macOS. These Linux setup instructions have not yet been validated by a full project test run on a Linux host.

### Start the browser workspace

```sh
python3 suite.py serve
```

Open [http://127.0.0.1:8765](http://127.0.0.1:8765). Keep the terminal running while using the page. The Python process runs the local backend; opening `web/index.html` directly will not run experiments. No frontend build or npm command is needed.

The C++ engines build automatically when needed. You can start with memory, scheduling, and linking before installing OCaml or QEMU. Once OCaml is installed, compilation works without QEMU too; machine execution will be reported as unavailable until QEMU is present.

To build all engines explicitly, including the OCaml compiler:

```sh
python3 suite.py build
```

If port 8765 is occupied, use `python3 suite.py serve --port 8766` and open port 8766 instead. Press Ctrl+C in the server terminal to stop it. The server listens only on the local computer.

## Browser: Learn

Start here if you are new to systems programming.

1. Start the server and open the browser workspace.
2. Select **Virtual memory** in the sidebar and keep **Learn** selected. Read the introduction to pages and physical frames.
3. Click **Start guided experiment**. Use **Next access** to watch pages enter memory, and read the explanation beside the frames. The first four accesses produce three page faults and one hit.
4. Continue to the prediction step. Choose which page you think FIFO will replace, reveal the result, and compare it with your reasoning. You can revise an answer.
5. Follow the remaining sections to try Clock and investigate whether more frames always mean fewer faults. Open **Field notes** whenever a term is unfamiliar.
6. Enter **Lab** to change the workload yourself, or choose another module from the sidebar.

In the other modules, the lesson moves through **Meet the idea**, **Watch it happen**, **Make a prediction**, **Compare and explain**, and **Try your own**. Use **Next event**, **Back**, **Reset**, and **Play** to inspect the trace. Each event comes from the backend simulation.

For a natural progression, try page replacement first, then address spaces, CPU scheduling, disk scheduling, linking, and compilation. This is a suggested route, not an enforced order. Lesson completion is a local progress marker.

## Browser: Lab

Use Lab when you want to choose the inputs and investigate the results.

1. Select a module and switch to **Lab**. A working example is loaded for you.
2. Inspect its inputs. Memory uses page-reference and frame controls; scheduling, address spaces, and linking use a workload JSON editor. Compilation has a source editor.
3. Change one input at a time. For example, in **CPU scheduling**, select `rr` and change `quantum` from `2` to `1` in the workload JSON, leaving the process list unchanged.
4. Click **Apply and run**. In the introductory memory workspace, the corresponding button is **Apply & reset**. A successful application builds a new trace at step zero; a failed edit preserves the last successful result and your draft.
5. Step through the result and read the current-event explanation. CPU has a timeline, disk has a head path, VM has frames and page tables, and linking has symbol and relocation tables.
6. For CPU, disk, or address spaces, click **Compare all policies** to compare complete runs of the same workload. Memory displays its six-policy comparison automatically. Linking and compilation expose stages and diagnostics instead of a policy comparison.
7. Use **Export config** to download the applied experiment as `experiment.json`. Memory calls this **Export JSON**. Use **Import JSON** in the matching module to load it again.

Full-run comparisons summarize the entire workload, regardless of the playback position. The current-event panel describes only the selected step. CPU `quantum` affects RR, PRIO, and PREPRIO; FCFS, LCFS, and SRTF ignore it.

The introductory memory visual lab supports up to 8 frames and 128 accesses. Its CLI supports up to 64 frames and 4096 accesses. Limits and field definitions for the other modules are in [Module models](docs/modules.md).

### Try the compiler

With OCaml installed, select **Compilation → Lab**, replace the source with this program, and click **Apply and run**:

```text
fn factorial(n) = if n <= 1 then 1 else n * factorial(n - 1);
factorial(6)
```

Inspect the tokens, syntax tree, semantic checks, reference result, assembly, and execution stages. The reference result is **720**. With **Execute with QEMU** enabled and QEMU installed, the machine result should also be 720 and the status should be `passed`. Without QEMU, you can still inspect the front end and generated code.

The execution stage offers **Download assembly** and **Download ELF**. Other than introductory memory, every workspace also offers **Export full trace**, which includes all events, even those you have not visited.

### Continue a browser experiment in the CLI

Export a configuration, move the downloaded `experiment.json` into the directory containing `suite.py`, then run:

```sh
python3 suite.py shell experiment.json
```

This loads the same inputs into an interactive terminal session. You can also pass a quoted path to a file elsewhere. No web server is required for this step.

Learn and Lab retain separate sessions for CPU, disk, address spaces, linking, and compilation until the page reloads. The introductory memory lesson offers a restore action for its previous Lab experiment. Export configurations to keep experiments across reloads; local lesson completion does not save workloads.

## Interactive command line

The interactive shell provides direct control over inputs, playback, comparisons, and files. You can use it independently of the browser.

1. Open a terminal in the directory containing `suite.py`.
2. Run `python3 suite.py list` to see the modules and policies.
3. Open an example with `python3 suite.py shell --module cpu`. Replace `cpu` with `memory`, `vm`, `disk`, `linker`, or `compiler` to choose another module. With no module, the shell opens introductory memory.
4. Use `config` to inspect inputs and `help` to see the available commands.
5. Step through the trace, change parameters, and compare policies. Applying an input change resets playback to zero.
6. Save the configuration or export the full trace, then type `quit` or press Ctrl+D.

For example, start a CPU session:

```sh
python3 suite.py shell --module cpu
```

At the `cpu>` prompt, enter the following commands. The block contains commands only; do not type the prompt itself.

```text
config
step 3
back
state
set policy rr
set quantum 1
run
compare rr srtf
save cpu-experiment.json
export cpu-trace.json
quit
```

This changes Round Robin's time slice, inspects the completed run, compares it with SRTF, and saves both the inputs and the event trace. Comparisons leave your active configuration and playback position unchanged.

To resume from the saved inputs or verify and replay the saved trace:

```sh
python3 suite.py shell cpu-experiment.json
python3 suite.py replay cpu-trace.json
```

These commands each start a session; leave the first with `quit` before running the second. Replay recomputes the experiment and checks that its trace matches before opening it at step zero.

### Shell command reference

| Command | Purpose |
| --- | --- |
| `help`, `help set`, `policies` | Inspect commands and policies available in this module |
| `config`, `load PATH` | Inspect or replace the current module's input |
| `set FIELD VALUE` | Change a field and rebuild the trace |
| `step 3`, `back 2`, `goto 5` | Navigate completed events; `goto 0` is the initial state |
| `run`, `reset` | Move to the final or initial state |
| `state`, `explain`, `trace 10` | Inspect the current snapshot or recent visited events |
| `summary` | Show current-position metrics in `memory`, full-run metrics in the other modules |
| `compare`, `compare fifo clock` | Compare policies supported by the current module |
| `sweep 2 3 4` | Compare frame counts in `memory` or `vm` |
| `source PATH` | Load source in a compiler session |
| `save PATH`, `export PATH` | Save the configuration or the complete trace |
| `replay PATH` | Verify and open a saved trace for the current module |
| `quit`, Ctrl+D | End the session |

Use single quotes around JSON values containing spaces or double quotes. For example, in a CPU session:

```text
set processes '[{"arrival":0,"priority":2,"bursts":[3,2,1]},{"arrival":1,"bursts":[2]}]'
```

In a memory session, `refs w1 2 r2 3` replaces the access sequence. Bare numbers and `r7` read a page; `w7` writes it. Saved memory JSON uses zero-based access indices in `writes`, not page numbers. In a compiler session, `source examples/functions.suite` loads the included source file.

A shell stays within one module. To change modules, quit and start another shell. Invalid commands preserve the current experiment, and a blank line does nothing. Ctrl+C cancels the current command and returns to the prompt. Python's `cmd` support provides command history and completion in interactive terminals.

Quote paths containing spaces. Output files are preserved by default; explicitly add `--force` to overwrite one, such as `save cpu-experiment.json --force`.

## Batch experiments

Batch commands run once and exit. Use them for repeatable comparisons, scripts, or exporting data for analysis.

1. Choose an example from `examples/`, or export a configuration from the browser or interactive shell.
2. Run the configuration with `run` to produce its complete event trace.
3. Use `compare` for scheduling/replacement policies, optionally supplying algorithms or frame counts.
4. Choose `--format table` for terminal reading, `json` for structured output, or `csv` for tabular analysis.
5. Add `--output PATH` to save the result. Add `--force` only when you intend to overwrite an existing file.

Run a single experiment:

```sh
python3 suite.py run examples/vm.json --format table
```

Compare all CPU or disk schedulers on their default workloads:

```sh
python3 suite.py compare --module cpu --format table
python3 suite.py compare --module disk --format csv --output disk-comparison.csv
```

Explore a known page-replacement counterexample:

```sh
python3 suite.py compare examples/belady.json --algorithms fifo --frame-counts 3 4 --format table
```

FIFO produces **9 faults with 3 frames** and **10 faults with 4 frames** on this workload. Keeping the input fixed makes the effect of the frame count visible.

Run a VM frame sweep or save a linker trace:

```sh
python3 suite.py compare --module vm --algorithms fifo clock --frame-counts 2 3 4
python3 suite.py run --module linker --output link-trace.json
```

Compile a source file and verify its RISC-V result, or explicitly omit machine execution:

```sh
python3 suite.py run --module compiler --source-file examples/functions.suite
python3 suite.py run --module compiler --source-file examples/functions.suite --no-verify
```

The compiler's JSON output includes the reference result, verification status, assembly, and an `artifact_id`. Generated files are in `build/artifacts/<artifact_id>/program.s` and `program.elf`. Both commands require OCaml; `--no-verify` removes the need to execute QEMU.

You can also script an interactive session by placing shell commands in a text file, one per line. The included memory session can be run with:

```sh
python3 suite.py shell examples/mixed-writes.json < examples/session.txt
```

A redirected session returns a nonzero exit status if a command fails. In batch mode, `run` defaults to JSON events and metadata; `compare` defaults to JSON summary rows. For CSV, `run` exports flattened event rows and `compare` exports summary rows. Full state snapshots remain in JSON.

Flags such as `--policy`, `--quantum`, `--head`, `--frames`, and `--page-size` override a configuration without modifying its file. A flag from another module is rejected. `compare` applies to memory, VM, CPU, and disk; linking and compilation have no scheduling policies to compare.

## Troubleshooting

| Symptom | What to check |
| --- | --- |
| Python cannot find `suite.py` | Run commands from the directory that contains it |
| C++ compiler is missing | Install a C++17 compiler or set `CXX` to its executable name |
| `ocamlc` is missing | Install OCaml for compilation or the full `build` command; use `serve` to explore the other modules |
| QEMU status is `unavailable` | Check `qemu-system-riscv64 --version`; install it to enable machine execution |
| Browser cannot reach the backend | Keep `serve` running and open its HTTP URL rather than `index.html` |
| The server port is already in use | Choose another port with `--port` and use that port in the browser URL |
| An export says the file exists | Choose a new filename or explicitly use `--force` |
| A saved trace fails replay verification | Re-run its configuration; engine changes or a different compiler verification environment can change the trace |

## Models and limits

These experiments describe explicit systems models. CPU time uses integer units and zero context-switch cost; disk time counts track movement. VM tracks residency and metadata, not page contents or actual storage I/O. The linker uses a teaching object format with opaque opcodes, separate from ELF linking. The results are simulator observations rather than host operating-system benchmarks.

The compiler implements an integer expression language with bindings, conditionals, comparisons, and functions, including recursion. OCaml is its implementation language; the source input is the suite's own language. Generated RV64IM ELF files run on QEMU's `virt` machine with a bare-metal entry point and do not use the Linux syscall ABI. Missing or disabled QEMU execution is reported explicitly, and `verified` is true only when machine execution passes the reference comparison.

[Module models](docs/modules.md) document input schemas, limits, tie-breaking, event boundaries, diagnostic fallbacks, and language semantics. [Memory policy definitions](docs/memory-model.md) describe sampling and replacement in detail. [Learning design](docs/learning-design.md) explains how the guided lessons connect concepts to experiments.

## Implementation and validation

```text
core/                  Shared C++ page-replacement state machine and standalone adapter
native/                C++ CPU, disk, linker, and multi-process VM engines
compiler/              OCaml lexer, parser, semantic checks, interpreter, RV64 code generator
compiler_driver.py     Instruction encoding, ELF packaging, QEMU comparison
engine.py              Shared dispatch, memory configuration, comparisons, trace files
module_api.py          Module schemas, native input adapters, native build
session.py             Memory shell and shared navigation/file commands
experiment_session.py  Interactive sessions for the other modules
reports.py             Table and CSV output
suite.py               CLI routing and local HTTP API
web/                   Learn and Lab workspaces
examples/              Deterministic module inputs
tests/                 Golden cases, invariants, CLI, HTTP, and QEMU checks
```

With the full toolchain installed, run:

```sh
python3 suite.py build
python3 -m unittest discover -s tests -v
```

Tests compare against handwritten expected traces and results, verify invariants across generated workloads, check CLI/HTTP parity and replay, and execute generated RISC-V programs in QEMU when it is installed. HTTP tests need local socket access. Skipped dependencies are reported explicitly.

The recorded macOS validation passed **62 tests**, including **21 programs executed in QEMU**. See the [validation record](docs/validation.md) for the tested environment, browser checks, and verification scope.
