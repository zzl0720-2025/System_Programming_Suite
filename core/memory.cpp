#include "memory.hpp"

#include <algorithm>
#include <array>
#include <random>
#include <stdexcept>

namespace suite {
namespace {

const std::array<std::string, 6> policies = {
    "fifo", "random", "clock", "nru", "aging", "working-set"
};

void check_input(const std::string& algorithm, int capacity,
                 const std::vector<int>& references, const MemoryOptions& options) {
    if (std::find(policies.begin(), policies.end(), algorithm) == policies.end()) {
        throw std::invalid_argument("Unknown replacement policy.");
    }
    if (capacity < 1 || capacity > 64) {
        throw std::invalid_argument("Frame count must be between 1 and 64.");
    }
    if (references.empty() || references.size() > 4096) {
        throw std::invalid_argument("Provide between 1 and 4096 page references.");
    }
    for (int page : references) {
        if (page < 0 || page > 999) {
            throw std::invalid_argument("Page numbers must be between 0 and 999.");
        }
    }
    if (options.reset_interval < 1 || options.reset_interval > 4096 ||
        options.window < 1 || options.window > 4096) {
        throw std::invalid_argument("Reset interval and working-set window must be 1 to 4096 accesses.");
    }
    auto writes = options.writes;
    std::sort(writes.begin(), writes.end());
    if (std::adjacent_find(writes.begin(), writes.end()) != writes.end()) {
        throw std::invalid_argument("Write indices must not repeat.");
    }
    for (int index : writes) {
        if (index < 0 || index >= static_cast<int>(references.size())) {
            throw std::invalid_argument("A write index is outside the reference sequence.");
        }
    }
}

void sample(std::vector<Frame>& frames, const std::string& algorithm,
            int time, int interval, std::vector<int>& cleared) {
    if (time == 0 || time % interval != 0) return;
    if (algorithm != "nru" && algorithm != "aging") return;
    for (int slot = 0; slot < static_cast<int>(frames.size()); ++slot) {
        auto& frame = frames[slot];
        if (frame.page < 0) continue;
        if (algorithm == "aging") {
            frame.age = (frame.age >> 1) | (frame.referenced ? (std::uint32_t{1} << 31) : 0);
        }
        if (frame.referenced) cleared.push_back(slot);
        frame.referenced = false;
    }
}

int choose_frame(std::vector<Frame>& frames, const std::string& algorithm,
                 int hand, int time, int window, std::mt19937& random,
                 std::vector<int>& cleared) {
    const int size = static_cast<int>(frames.size());
    // Free frames are consumed in hand order, regardless of replacement policy.
    for (int offset = 0; offset < size; ++offset) {
        const int slot = (hand + offset) % size;
        if (frames[slot].page < 0) return slot;
    }
    if (algorithm == "fifo") {
        int oldest=hand;
        for(int offset=1;offset<size;++offset) {
            int slot=(hand+offset)%size;
            if(frames[slot].loaded_at<frames[oldest].loaded_at) oldest=slot;
        }
        return oldest;
    }
    if (algorithm == "random") return static_cast<int>(random() % size);
    if (algorithm == "clock") {
        while (frames[hand].referenced) {
            frames[hand].referenced = false;
            cleared.push_back(hand);
            hand = (hand + 1) % size;
        }
        return hand;
    }
    if (algorithm == "nru" || algorithm == "aging") {
        auto rank = [&](int slot) -> std::uint32_t {
            const auto& frame = frames[slot];
            return algorithm == "aging" ? frame.age :
                   2 * static_cast<unsigned>(frame.referenced) + static_cast<unsigned>(frame.dirty);
        };
        int best = hand;
        for (int offset = 1; offset < size; ++offset) {
            int slot = (hand + offset) % size;
            if (rank(slot) < rank(best)) best = slot;
        }
        return best;
    }

    int oldest = -1;
    for (int offset = 0; offset < size; ++offset) {
        const int slot = (hand + offset) % size;
        auto& frame = frames[slot];
        if (frame.referenced) {
            frame.referenced = false;
            frame.last_seen = time;
            cleared.push_back(slot);
        } else if (time - frame.last_seen > window) {
            return slot;
        }
        if (oldest < 0 || frame.last_seen < frames[oldest].last_seen) oldest = slot;
    }
    return oldest;
}

} // namespace

MemoryMachine::MemoryMachine(std::string algorithm, int capacity, const MemoryOptions& options)
    : algorithm_(std::move(algorithm)), options_(options), random_(options.seed) {
    auto check=options; check.writes.clear();
    check_input(algorithm_,capacity,{0},check);
    frames_.resize(capacity);
}

MemoryEvent MemoryMachine::access(int page, bool write) {
    auto& frames=frames_;
    const auto& algorithm=algorithm_;
    const auto& options=options_;
    const int time=time_++, capacity=static_cast<int>(frames.size());
    auto& hand=hand_;
    std::vector<int> cleared;
    sample(frames, algorithm, time, options.reset_interval, cleared);
    const auto found = std::find_if(frames.begin(), frames.end(),
                                   [page](const Frame& frame) { return frame.page == page; });
    const bool hit = found != frames.end();
    int slot = hit ? static_cast<int>(found - frames.begin()) : -1;
    int victim = -1;
    bool writeback = false;
    if (!hit) {
        ++faults_;
        slot = choose_frame(frames, algorithm, hand, time, options.window, random_, cleared);
        victim = frames[slot].page;
        writeback = victim >= 0 && frames[slot].dirty;
        if (writeback) ++writebacks_;
        frames[slot] = {page, false, false, 0, time, time};
        hand = (slot + 1) % capacity;
    }
    frames[slot].referenced = true;
    if (write) frames[slot].dirty = true;
    return {time,page,slot,victim,faults_,hand,hit,cleared,frames,write,writeback,writebacks_};
}

void MemoryMachine::release(int page) {
    for(auto& frame:frames_) if(frame.page==page) frame=Frame{};
}

MemoryRun simulate_memory(const std::string& algorithm, int capacity,
                          const std::vector<int>& references, const MemoryOptions& options) {
    check_input(algorithm, capacity, references, options);
    MemoryRun run{algorithm, capacity, 0, references, {}, options, 0};
    MemoryMachine machine(algorithm,capacity,options);
    std::vector<bool> writes(references.size(),false);
    for(int index:options.writes) writes[index]=true;
    for(int i=0;i<static_cast<int>(references.size());++i) run.events.push_back(machine.access(references[i],writes[i]));
    run.faults=run.events.back().faults;
    run.writebacks=run.events.back().writebacks;
    return run;
}

} // namespace suite
