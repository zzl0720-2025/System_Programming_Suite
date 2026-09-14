# Learning design

The suite serves two workflows: a learner exploring a mechanism for the first time, and an experienced user running reproducible experiments. Both consume the same backend trace.

All modules are open immediately. Completion is a personal progress marker, not a prerequisite or an assessment certificate.

## Guided lessons

| Workspace | Prediction | Visible evidence | Follow-up experiment |
| --- | --- | --- | --- |
| Page replacement | Which FIFO page leaves? | Frames, hit/fault explanation, replacement log | Investigate Belady’s anomaly |
| Address spaces | Does P1 address 16 map to 4112? | Separate page tables and frame/offset calculation | Add frames, trigger protection and segmentation faults |
| CPU | Does arrival alone preempt Round Robin? | Timeline and ready/running/blocked table | Change quantum and compare response/waiting |
| Disk | Does FIFO choose track 10 or the nearest track? | Head path, request order, seek distance | Compare SSTF, LOOK, and frozen FLOOK batches |
| Linking | What address resolves a forward reference? | Pass-1 symbols and pass-2 original/resolved operands | Rename or reorder modules and inspect diagnostics |
| Compilation | What do interpreter and machine return? | Tokens, tree, checks, assembly, real QEMU result | Write recursive functions and repair semantic errors |

The introductory memory lesson uses its existing five-section flow. Each additional lesson follows: meet the idea, watch it happen, make a prediction, compare and explain, try your own. Examples are fixed so explanations stay tied to actual inputs. Learners can inspect the example JSON without editing it.

Wrong answers give a reason and allow another attempt. Predictions can be revealed. Step navigation is unrestricted. The new lessons use explicit self-marked completion; the introductory memory lesson retains its final conceptual question. None gates module access.

## Experiment workspaces

Lab exposes policy selection and documented workload JSON, or source text for the compiler. This keeps the expert interface aligned with the CLI. Failed edits preserve the last successful trace and the draft. Applying valid input rebuilds the trace and resets its cursor. Learn and Lab keep separate sessions for the new modules; module switching preserves each session until reload.

Step, back, reset, play, and direct timeline/stage selection inspect recorded state. Playback pauses on mode changes, module changes, and field notes. Current-event explanations stay beside the visualization. Full-run metrics are explicitly labeled as independent of playback.

Comparisons hold the workload fixed. Memory and VM compare six replacement policies; CPU compares six schedulers; disk compares five. Linking and compilation expose stages and diagnostics instead of a meaningless policy ranking.

Exported configurations can be loaded by the interactive CLI. Complete traces can be recomputed and verified before replay. Compiler artifacts are actual assembly and ELF files, not illustrative downloads.

## Presentation

Use a plain-language explanation before specialized terms. Keep prediction choices short. Define model limitations where they affect interpretation: disk movement is not SSD performance; VM does not store bytes; teaching relocation is separate from ELF linking; QEMU results describe bare-metal execution.

Each workspace has module-specific field notes. Controls use labels and keyboard focus styles. The modal notes drawer makes background controls inert. An announcer describes stepped events. On narrow screens, explanation and simulator stack and wide tables scroll inside their containers. Colors supplement process IDs and textual states.

Lesson completion is stored in local browser storage. No accounts, analytics, scores, or remote submission are required. Experiments persist through export rather than automatic server storage.
