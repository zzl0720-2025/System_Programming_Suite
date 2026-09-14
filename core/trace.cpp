#include "memory.hpp"

#include <iostream>

namespace suite {
namespace {

void integers(const std::vector<int>& values) {
    std::cout << '[';
    for (std::size_t i = 0; i < values.size(); ++i) {
        if (i) std::cout << ',';
        std::cout << values[i];
    }
    std::cout << ']';
}

const char* boolean(bool value) { return value ? "true" : "false"; }

} // namespace

void write_json(const MemoryRun& run) {
    auto& out = std::cout;
    out << "{\"schema_version\":1,\"module\":\"memory\",\"model\":\""
        << (run.options.writes.empty() ? "single-process-read-only" : "single-process-read-write")
        << "\",\"algorithm\":\"" << run.algorithm << "\",\"frames\":" << run.capacity
        << ",\"seed\":" << run.options.seed
        << ",\"reset_interval\":" << run.options.reset_interval
        << ",\"window\":" << run.options.window << ",\"writes\":";
    integers(run.options.writes);
    out << ",\"references\":";
    integers(run.references);
    out << ",\"summary\":{\"accesses\":" << run.references.size()
        << ",\"faults\":" << run.faults
        << ",\"hits\":" << run.references.size() - run.faults
        << ",\"writebacks\":" << run.writebacks << "},\"events\":[";
    for (std::size_t i = 0; i < run.events.size(); ++i) {
        const auto& event = run.events[i];
        if (i) out << ',';
        out << "{\"index\":" << event.index << ",\"page\":" << event.page
            << ",\"slot\":" << event.slot << ",\"victim\":" << event.victim
            << ",\"faults\":" << event.faults << ",\"hand\":" << event.hand
            << ",\"hit\":" << boolean(event.hit)
            << ",\"write\":" << boolean(event.write)
            << ",\"writeback\":" << boolean(event.writeback)
            << ",\"writebacks\":" << event.writebacks << ",\"cleared\":";
        integers(event.cleared);
        out << ",\"frames\":[";
        for (std::size_t j = 0; j < event.frames.size(); ++j) {
            const auto& frame = event.frames[j];
            if (j) out << ',';
            out << "{\"page\":" << frame.page << ",\"referenced\":" << boolean(frame.referenced)
                << ",\"dirty\":" << boolean(frame.dirty) << ",\"age\":" << frame.age
                << ",\"last_seen\":" << frame.last_seen << '}';
        }
        out << "]}";
    }
    out << "]}\n";
}

} // namespace suite
