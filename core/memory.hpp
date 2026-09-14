#pragma once

#include <cstdint>
#include <random>
#include <string>
#include <vector>

namespace suite {

struct Frame {
    int page = -1;
    bool referenced = false;
    bool dirty = false;
    std::uint32_t age = 0;
    int last_seen = 0;
    int loaded_at = 0;
};

struct MemoryOptions {
    std::uint32_t seed = 1;
    int reset_interval = 4;
    int window = 4;
    std::vector<int> writes;
};

struct MemoryEvent {
    int index;
    int page;
    int slot;
    int victim;
    int faults;
    int hand;
    bool hit;
    std::vector<int> cleared;
    std::vector<Frame> frames;
    bool write;
    bool writeback;
    int writebacks;
};

struct MemoryRun {
    std::string algorithm;
    int capacity;
    int faults = 0;
    std::vector<int> references;
    std::vector<MemoryEvent> events;
    MemoryOptions options;
    int writebacks = 0;
};

class MemoryMachine {
    std::string algorithm_;
    MemoryOptions options_;
    std::vector<Frame> frames_;
    std::mt19937 random_;
    int hand_ = 0, time_ = 0, faults_ = 0, writebacks_ = 0;
public:
    MemoryMachine(std::string algorithm, int capacity, const MemoryOptions& options);
    MemoryEvent access(int page, bool write);
    void release(int page);
    const std::vector<Frame>& frames() const { return frames_; }
};

MemoryRun simulate_memory(const std::string& algorithm, int capacity,
                          const std::vector<int>& references,
                          const MemoryOptions& options = {});
void write_json(const MemoryRun& run);

} // namespace suite
