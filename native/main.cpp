#include "engines.hpp"
#include <iostream>
#include <stdexcept>

int main(int argc, char** argv) {
    try {
        if (argc != 2) throw std::invalid_argument("Choose cpu, disk, linker, or vm.");
        const std::string module = argv[1];
        Json result;
        if (module == "cpu") result = simulate_cpu(std::cin);
        else if (module == "disk") result = simulate_disk(std::cin);
        else if (module == "linker") result = link_modules(std::cin);
        else if (module == "vm") result = simulate_vm(std::cin);
        else throw std::invalid_argument("Unknown module.");
        if (!std::cin) throw std::invalid_argument("Incomplete native input.");
        std::cout << result.dump() << '\n';
    } catch (const std::exception& error) {
        std::cerr << error.what() << '\n';
        return 2;
    }
}
