# Module models

All experiments are JSON objects with `schema_version: 1` and a `module` name. Unknown fields are rejected, booleans are not accepted as integers, and normalized inputs include defaults. The files in `examples/` are executable schema examples.

Results have `module`, `schema_version`, `events`, and `summary`. New modules also include a normalized `config`. Events contain a zero-based `index`. The shell’s cursor counts completed events; a cursor of zero has not applied any event. Summary values describe the complete run in new modules.

## CPU scheduling

Fields: `algorithm`, `quantum` (default 2), and `processes`. Each process has `arrival`, `priority` (default 1), and an odd-length `bursts` list alternating CPU and I/O. IDs are input indices. Larger priority values win.

Limits: 1–32 processes, arrival 0–1000, priority 0–31, quantum 1–1000, 1–31 bursts of 1–1000 units. The sum of all burst durations plus the final arrival must be at most 10000.

| Policy | Decision |
| --- | --- |
| FCFS | Run the oldest ready process until it blocks or finishes |
| LCFS | Run the most recently enqueued ready process without preemption |
| SRTF | Run the process with the least total CPU time remaining; preempt for a strictly smaller remainder |
| RR | Rotate the ready queue after a quantum, block, or completion |
| PRIO | Select the highest dynamic priority in the active queue; time slicing but no arrival preemption |
| PREPRIO | PRIO plus preemption when an active ready process has a strictly higher dynamic priority |

At each integer time, arrivals and I/O completions enter the ready queue in process ID order. The scheduler checks preemption, dispatches if necessary, counts ready waiting, and executes one CPU unit. Completion, blocking, or quantum expiration occurs at the interval’s end. A quantum requeue at time T therefore precedes arrivals admitted at T in the next iteration. Equal policy ranks use enqueue order. Equal remaining CPU work or equal priority does not cause preemption.

Priority scheduling starts at the configured static priority. Quantum expiration and forced priority preemption decrement dynamic priority. Going below zero restores the static value and places the process in the expired queue. I/O completion resets priority and rejoins active. Expired and active queues swap only when dispatch needs work and active is empty; a running process does not trigger an early swap. Each dispatch starts a fresh quantum. The quantum is ignored by FCFS, LCFS, and SRTF.

I/O runs independently for each blocked process; there is no shared I/O device queue. Context switches cost zero. `remaining` counts all future CPU work, excluding I/O. Event `ready` is the set of waiters during the interval, while `processes` is a snapshot after it; an expiring process can therefore be ready in the snapshot without having waited during that interval. `arrivals` includes I/O completions.

Waiting counts ready but non-running time. Response is first dispatch minus arrival. Turnaround is completion minus arrival. `utilization` is CPU work divided by elapsed time from time zero, including initial idle time. `dispatches` counts every dispatch, even if the same process is selected again.

## Disk scheduling

Fields: `algorithm`, `head` (default 0), and `requests`, each containing `arrival` and `track`. IDs are input indices. Limits: 1–128 requests, tracks/head 0–9999, arrivals 0–100000.

Requests are stable-sorted by arrival. At each decision, admit all arrived requests. FIFO takes the first waiting request; SSTF takes the closest. LOOK starts upward and reverses only when no request is eligible in that direction. CLOOK keeps moving upward and wraps to the lowest waiting track when necessary. The entire wrap distance is charged. FLOOK applies LOOK to a frozen active batch while admitting new requests into a separate incoming batch; swap batches only when active empties. FLOOK keeps its current direction across swaps. Ties use queue order.

A dispatch is non-preemptive. Travel costs `abs(destination - head)` time units; a zero-distance request completes immediately. When no request is ready, an idle event advances to the next arrival. Arrivals during travel are admitted at the next decision. Event `queue` and `incoming` represent dispatch-time queues after removal of the chosen request. The browser’s request-state table describes the end of the selected event.

The model excludes rotation, transfer time, caching, and SSD behavior. Waiting is dispatch minus arrival; turnaround includes travel. `movement` is total travel and `utilization` is movement divided by elapsed time, or zero if time is zero.

## Two-pass linker

Fields: `memory_limit` (default 256) and `modules`. Each module has a unique identifier `name`, `definitions` mapping symbols to local offsets, and nonempty `code`. An instruction has `mode`, `opcode` (default 0), `value` (default 0), and `target` only for E/M. Names are ASCII identifiers of at most 32 characters.

Limits: 1–32 modules; 1–1024 instructions and at most 128 definitions per module; total instructions must fit `memory_limit` (1–65536). Opcodes are opaque integers 0–99. Operands are signed 32-bit integers. A memory address denotes an instruction slot, not a byte address.

Pass 1 assigns consecutive module bases and records symbols. Pass 2 visits instructions in layout order:

| Mode | Resolution | Error fallback |
| --- | --- | --- |
| I | Keep the signed literal | No address check |
| A | Absolute address within `[0, memory_limit)` | Zero |
| R | Current module base + local offset | Current module base |
| E | Symbol address + addend within address space | Zero if undefined or out of range |
| M | Named module base + offset within that module | Zero if module missing; target module base if offset invalid |

The first duplicate symbol definition wins and later definitions produce errors. A definition outside its own module is corrected to offset zero with an error. Unused definitions produce warnings. Reference errors are diagnostics in a successful result so later instructions remain inspectable; malformed JSON/schema inputs reject the run. `summary.errors` distinguishes a clean link from a completed link containing recoverable errors.

Pass-1 events carry the symbol table built so far; pass-2 events carry original and resolved operands. Final results include a combined memory map and all diagnostics. This teaching object format is separate from the real RISC-V ELF image emitted by the compiler pipeline.

## Virtual address spaces

Fields: `algorithm`, `frames` (default 3), `page_size` (4096), `seed` (1), `reset_interval` (4), `window` (4), `processes`, and `instructions`.

Each process has `pid` and non-overlapping `areas`. Areas contain `start` and exclusive `end` page numbers plus optional booleans `read_only` and `file_mapped`. Instructions use `op: switch|read|write|exit`, `pid`, and a byte `address` for reads/writes. Accesses implicitly switch to the specified process if needed; explicit `switch` is also available.

Limits: 1–8 processes, unique IDs 0–999, 64 virtual pages per process, 1–32 physical frames, 1–256 instructions. Page size is a power of two from 256 to 65536. Read/write addresses are nonnegative signed 32-bit integers; unmapped values remain valid experiment inputs so a segmentation fault can be demonstrated.

Translation uses `page = address / page_size`, `offset = address % page_size`, then `physical = frame * page_size + offset`. Each process has its own table. The replacement pool is global across processes, and all six policies use the same `MemoryMachine` as the introductory memory module.

A valid missing page faults and obtains a frame. Dirty victims produce `swap-out` for anonymous pages or `file-out` for file-backed pages. Loads use `swap-in` if an anonymous backing copy exists, otherwise `zero-fill`; file-backed loads use `file-in`. A swapped flag records that a backing copy exists, so it can remain true while a page is resident. Contents and file identities are not simulated; file-backed pages do not share frames.

A protected write can first fault and load the page, then is rejected without setting the dirty bit. The event’s physical address is the translation result, not evidence that the write executed. Hits/faults include these valid translations; `protection_faults` separately counts rejected writes. Unmapped addresses allocate nothing. Access to an exited process also increments the segmentation-fault counter.

Exit unmaps that process’s frames, writes back dirty file-backed pages, discards anonymous pages and swap metadata, and clears its table. It does not implicitly switch address spaces. Switch counts increment only when the current PID changes. Page-replacement sampling time counts valid page accesses, excluding switches, exits, and invalid addresses.

Snapshots expose physical frames and touched page-table entries, including present/reference/dirty/swapped/protection/file flags. Unvisited virtual pages are omitted. All VM frame indices start at zero in the browser, JSON, and CLI; the introductory memory desk uses one-based display labels.

## Compiler language and execution

Fields: `source` (1–8192 bytes) and `verify` (default true). The implementation is in OCaml; the input is the suite’s own small language.

```text
fn factorial(n) = if n <= 1 then 1 else n * factorial(n - 1);
let input = 6 in factorial(input)
```

Programs contain zero or more top-level function definitions followed by an expression. Functions have up to four parameters and support forward calls, mutual recursion, and ordinary recursion. Expressions include signed integer literals, lexical variables, unary minus, `let ... in ...`, `if ... then ... else ...`, calls, parentheses, `+ - * / %`, and `== != < > <= >=`. `#` starts a line comment. There are no strings, loops, assignment, arrays, closures, or external calls.

Arithmetic wraps at signed 32 bits. Comparisons return 0 or 1. Any nonzero condition is true; only the selected branch is evaluated. Division truncates toward zero. To match RISC-V word operations, division by zero returns -1, remainder by zero returns the dividend, and `INT_MIN / -1` returns `INT_MIN` with remainder zero.

The lexer reports token positions. The parser checks syntax and precedence; semantic checks reject duplicate functions/parameters, undefined names, and wrong argument counts. Lexical and parse errors include source positions; semantic diagnostics currently identify names without source spans. The reference interpreter has a 50000-expression fuel budget and a depth limit of 256. Syntax nesting is limited to 100 and tokens to 2048 including the end marker. Exceeding a limit rejects the run rather than producing an unverified result.

Code generation uses RV64IM word arithmetic, a stack, direct function calls, and conditional branches. Stack slots are 16-byte aligned. The small encoder in `compiler_driver.py` handles the emitted instruction subset, resolves labels, checks immediates, and writes an ELF64 RISC-V executable. It is not a general-purpose assembler or ELF linker.

QEMU runs with `-machine virt -accel tcg -cpu rv64 -m 128M -bios none`. The image enters at `0x80000000`, sets a stack, prints eight hexadecimal digits and a newline through the UART, and signals the test finisher. The driver converts that output to a signed 32-bit value and compares it with the interpreter. This is bare-metal machine execution, not Linux user-mode execution or Linux ABI validation.

Verification statuses are `passed`, `failed`, `unavailable`, `not-requested`, or `timeout`. A timeout is ten seconds. `verified` is true only for `passed`. Generated `program.s` and `program.elf` files are stored under `build/artifacts/<content-hash>/` and can be downloaded from the browser.

Primary references: [RISC-V instruction set](https://docs.riscv.org/reference/isa/unpriv/rv-32-64g.html), [QEMU RISC-V target](https://www.qemu.org/docs/master/system/target-riscv.html), and [QEMU virt machine](https://www.qemu.org/docs/master/system/riscv/virt.html).

## HTTP interface

- `GET /api/health`: available modules and tool presence.
- `GET /api/examples`: normalized deterministic examples.
- `GET /api/policies`: introductory memory policy descriptions.
- `POST /api/run`: one experiment, returning its trace.
- `POST /api/compare`: one scheduling/memory experiment, returning all policy summaries.
- `GET /api/artifacts/<24-hex-hash>/program.s` or `program.elf`: a generated artifact.

POST bodies use `application/json` and are limited to 256 KiB. Invalid experiments return status 400 with a JSON `error`. Linker semantic diagnostics are part of a status-200 result. The server is intended for local use, not deployment as a public multiuser execution service.
