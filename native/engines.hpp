#pragma once
#include "json.hpp"
#include <istream>

Json simulate_cpu(std::istream& input);
Json simulate_disk(std::istream& input);
Json link_modules(std::istream& input);
Json simulate_vm(std::istream& input);
