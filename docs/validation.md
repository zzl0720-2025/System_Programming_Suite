# Validation record

Verified on macOS on September 13, 2026. Toolchain: C++17 with Apple Clang, OCaml 5.4.0, Python 3.11, and QEMU 11.1.1 (`qemu-system-riscv64`).

## Automated checks

```sh
python3 -m unittest discover -s tests -v
```

**62 tests passed, with no skips** in the final run. HTTP tests were run with local socket access. Both C++ engines build with `-Wall -Wextra -pedantic`. The browser scripts pass Node’s syntax checks.

| Area | Evidence |
| --- | --- |
| Original memory behavior | All 28 existing tests retained and passing after extraction of `MemoryMachine` |
| Replacement policies | FIFO independent queue comparison, Clock second chance, seeded random draws, NRU classes, Aging boundaries, Working Set window/fallback, dirty eviction, Belady’s anomaly |
| CPU | Handwritten traces for all six policies, idle/I/O timing, equal-remainder behavior, quantum/arrival ordering, active/expired priorities |
| CPU invariants | 12 generated workloads × 6 policies; per-process CPU conservation, turnaround = waiting + CPU + I/O, response and first-dispatch consistency |
| Disk | Exact service orders and distances for all five policies, FLOOK batch isolation, CLOOK charged wrap, zero-distance and idle cases |
| Linker | All five modes, forward references, reordered layout, duplicate and out-of-range definitions, unresolved targets and deterministic fallback operands |
| VM | Process isolation and physical offsets, swap reload, dirty file exit, protection without dirtying, invalid/exited accesses, FIFO order after freeing a hole, page-table/frame agreement for all six policies |
| Compiler | 21 handwritten programs with expected reference values and **21 actual QEMU executions**, including recursive/mutual calls, nested arguments, shadowing, precedence, comparisons, signed overflow and division edge cases |
| Compiler diagnostics | Lexer/parser/semantic/evaluation failures, token positions, missing-QEMU status, ELF header and known instruction words |
| CLI and sessions | Library/CLI parity, JSON/table/CSV, stepping and rewind, failed edits preserving state, comparisons, overwrite protection, verified trace replay and tamper rejection |
| HTTP | Complete example catalog, all-module run parity, comparisons, JSON errors and recovery, assembly/ELF downloads |
| Native adapters | Truncated CPU, disk, linker, and VM input is rejected |

The QEMU test does not accept a matching interpreter value alone. It requires QEMU to exit successfully and print the independently expected value. Every one of the 21 golden programs passed machine execution in this environment. On a machine without QEMU, that test is explicitly skipped and runtime verification reports `unavailable`.

## Browser checks

The local web workspace was exercised through its actual controls at desktop width:

- Open every module directly without completing the initial memory lesson.
- CPU: choose the Round Robin prediction, reveal two time units, switch to Lab, apply SRTF, step through preemption, and compare all six schedulers.
- Disk: step through the head path, compare all five algorithms, then reveal FIFO’s first destination of track 10 and distance 40.
- Linking: reveal the forward reference to `add`, inspect its address 3 in the symbol table, and compare the original and resolved operand.
- VM: reveal P1 virtual address 16 mapping to physical address 4112 while P0 retains its separate page-0 frame.
- Confirm the final module-specific field-notes drawer explains CPU terms and removes background controls from the accessibility tree.
- Compiler: reveal reference/QEMU result 42; edit the source to an undefined variable and confirm that the error preserves the successful trace; repair it with recursive factorial and observe reference/QEMU result 720.

A final redirected shell smoke run also completed step/back/run/summary/quit for all six workspace modules with exit status zero.

These are manual browser checks, not an automated browser regression suite. The existing introductory memory interaction tests remain documented by the automated core/session cases; previous browser checks covered its lesson completion, dirty bits, anomaly comparison, import errors, and Lab restoration.

## Scope of verification

The RISC-V result is real bare-metal RV64IM execution on QEMU’s `virt` machine. This record does not claim Linux user-mode ABI validation, a Linux host test run, a general-purpose compiler, or compatibility of the teaching linker with ELF object files.

The current browser pass used a desktop viewport. Physical mobile devices and screen-reader behavior have not been tested. Responsive styles are provided, but they are not evidence of device testing.
