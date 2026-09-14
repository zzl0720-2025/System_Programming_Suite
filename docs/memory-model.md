# Memory model

## Shared rules

The `memory` module has one process, a fixed frame count, and a finite list of page accesses. Every page number is valid. Each access is a read unless its zero-based index appears in `writes`.

At access index `t`:

1. Apply a periodic sample if the policy needs one.
2. Look for the requested page in the resident frames.
3. On a miss, use an empty frame or choose a victim. Count a writeback if the victim is dirty.
4. Install a missing page with a cleared dirty bit, age 0, and timestamp `t`.
5. Set the resident page's reference bit to 1. On a write, also set its dirty bit to 1.
6. Record a snapshot after the access.

The scan hand starts at frame 0. Every load advances it to the frame after the chosen slot. Empty frames are consumed in hand order before any policy chooses a victim. Hits do not advance the hand. Equal ranks and equal sampled timestamps are resolved by scan order starting at the hand.

`index`, `slot`, `hand`, `cleared`, and `writes` use zero-based indices in JSON. CLI tables number accesses and frames starting at 1. `goto 0` means the empty state; `goto 1` means the state after the first access.

## FIFO

Replace the resident page with the earliest load timestamp. With no explicit unmapping, this is equivalent to replacing the frame at the hand. Tracking load time also preserves FIFO order in the `vm` module when process exit leaves holes in the frame array. Hits do not change that order.

## Random

Use the standard `std::mt19937` engine seeded with the configured unsigned 32-bit `seed`. On a miss with no free frame, take the next engine output modulo the frame count. Free-frame loads and hits consume no random values.

The modulo rule is deliberate so the result does not depend on a standard library's distribution implementation. For frame counts that do not divide 2^32, modulo reduction has a small sampling bias.

## Clock

Starting at the hand, clear each reference bit of 1 and advance. Replace the first frame with a reference bit of 0. A sweep can clear every frame before returning to its starting position. Every access, including a hit, sets the accessed page's bit to 1.

## NRU

Rank frames by `2 * referenced + dirty`, giving the classes:

| Rank | Referenced | Dirty |
| --- | --- | --- |
| 0 | No | No |
| 1 | No | Yes |
| 2 | Yes | No |
| 3 | Yes | Yes |

Choose the lowest rank, breaking ties in hand order. Reset reference bits before access `t` when `t > 0` and `t % reset_interval == 0`. Dirty bits persist until the page is evicted. The reset does not flush pages.

## Aging

Use a 32-bit unsigned counter per frame. At the same periodic boundary used by NRU, shift each resident counter right by one, place the frame's reference bit into bit 31, and clear the reference bit. Select the smallest counter, breaking ties in hand order.

The current access happens after sampling. A newly loaded page starts with age 0; it receives its first high bit at the next sample if still resident. A long interval can therefore cause a newly loaded page to be selected again before its first sample. This is part of the specified sampled model.

## Working Set

Scan once from the hand:

- If a frame is referenced, clear the bit and set its sampled timestamp to `t`.
- Otherwise, if `t - last_seen > window`, select it immediately.
- If no frame qualifies, select the oldest sampled timestamp after the scan, breaking ties in hand order.

Timestamps are approximate observations made during replacement scans, not exact last-access times. The strict `>` comparison means a page exactly at the age window is not yet selected by the threshold rule. It can still be chosen by the fallback.

## Output and interpretation

Each event contains the request, selected slot, victim if any, cumulative fault and writeback counts, cleared reference-bit positions, and the complete resulting frame state. `last_seen` is meaningful for Working Set; `age` is meaningful for Aging. Other policies carry those fields for a consistent frame representation.

A page fault in this model is a missing valid page. It is not an invalid-address exception. Writeback counts describe dirty evictions, not a disk queue, file contents, bytes written, or wall-clock performance. Dirty resident pages are left resident at the end of a workload, so policies can finish with different amounts of pending dirty data.

Comparison runs use identical references, write positions, seed, sampling interval, and window. Frame sweeps change only the frame count. Compare fault counts and writebacks together, keeping the end-of-workload rule in mind.

The `vm` module shares these policies through `MemoryMachine`; see [multi-process semantics](modules.md#virtual-address-spaces) for address translation, protection, and process exit.
