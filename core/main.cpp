#include "memory.hpp"

#include <iostream>
#include <stdexcept>
#include <string>
#include <vector>
#include <limits>

static int integer(const char* text) {
    std::size_t used = 0;
    int value = std::stoi(text, &used);
    if (used != std::string(text).size()) throw std::invalid_argument("Expected an integer.");
    return value;
}

int main(int argc, char** argv) {
    if (argc < 4) {
        std::cerr << "Usage: memory-engine <policy> <frames> [--seed N] [--reset N] [--window N] <page|wPAGE>...\n";
        return 2;
    }
    try {
        std::vector<int> references;
        suite::MemoryOptions options;
        for (int i = 3; i < argc; ++i) {
            const std::string token = argv[i];
            if (token == "--seed" || token == "--reset" || token == "--window") {
                if (++i == argc) throw std::invalid_argument("Missing option value.");
                if (token == "--seed") {
                    const std::string value = argv[i];
                    if (value.empty() || value.find_first_not_of("0123456789") != std::string::npos)
                        throw std::invalid_argument("Seed must be an unsigned 32-bit integer.");
                    auto seed = std::stoull(value);
                    if (seed > std::numeric_limits<std::uint32_t>::max())
                        throw std::invalid_argument("Seed must be an unsigned 32-bit integer.");
                    options.seed = static_cast<std::uint32_t>(seed);
                } else if (token == "--reset") options.reset_interval = integer(argv[i]);
                else options.window = integer(argv[i]);
            } else {
                const bool write = !token.empty() && token.front() == 'w';
                const bool prefixed = write || (!token.empty() && token.front() == 'r');
                if (write) options.writes.push_back(static_cast<int>(references.size()));
                references.push_back(integer(argv[i] + (prefixed ? 1 : 0)));
            }
        }
        suite::write_json(suite::simulate_memory(argv[1], integer(argv[2]), references, options));
    } catch (const std::exception& error) {
        std::cerr << error.what() << '\n';
        return 2;
    }
}
