#pragma once

#include <iomanip>
#include <map>
#include <sstream>
#include <string>
#include <variant>
#include <vector>

class Json {
    using Object = std::map<std::string, Json>;
    using Array = std::vector<Json>;
    std::variant<std::nullptr_t, bool, long long, double, std::string, Object, Array> value_;

    static std::string quote(const std::string& text) {
        std::ostringstream out;
        out << '"';
        for (unsigned char c : text) {
            if (c == '"' || c == '\\') out << '\\' << c;
            else if (c < 32) out << "\\u" << std::hex << std::setw(4) << std::setfill('0') << int(c);
            else out << c;
        }
        return out.str() + '"';
    }

public:
    Json() : value_(nullptr) {}
    Json(bool v) : value_(v) {}
    Json(int v) : value_(static_cast<long long>(v)) {}
    Json(long long v) : value_(v) {}
    Json(double v) : value_(v) {}
    Json(const char* v) : value_(std::string(v)) {}
    Json(std::string v) : value_(std::move(v)) {}
    static Json object(Object values = {}) { Json j; j.value_ = std::move(values); return j; }
    static Json array(Array values = {}) { Json j; j.value_ = std::move(values); return j; }
    Json& operator[](const std::string& key) {
        if (std::holds_alternative<std::nullptr_t>(value_)) value_ = Object{};
        return std::get<Object>(value_)[key];
    }
    void push(Json value) {
        if (std::holds_alternative<std::nullptr_t>(value_)) value_ = Array{};
        std::get<Array>(value_).push_back(std::move(value));
    }
    std::string dump() const {
        if (std::holds_alternative<std::nullptr_t>(value_)) return "null";
        if (const auto* v = std::get_if<bool>(&value_)) return *v ? "true" : "false";
        if (const auto* v = std::get_if<long long>(&value_)) return std::to_string(*v);
        if (const auto* v = std::get_if<double>(&value_)) { std::ostringstream s; s << std::setprecision(12) << *v; return s.str(); }
        if (const auto* v = std::get_if<std::string>(&value_)) return quote(*v);
        std::string result;
        if (const auto* v = std::get_if<Object>(&value_)) {
            for (const auto& [key, item] : *v) { if (!result.empty()) result += ','; result += quote(key) + ':' + item.dump(); }
            return '{' + result + '}';
        }
        for (const auto& item : std::get<Array>(value_)) { if (!result.empty()) result += ','; result += item.dump(); }
        return '[' + result + ']';
    }
};
