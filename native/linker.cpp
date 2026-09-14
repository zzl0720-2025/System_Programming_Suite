#include "engines.hpp"
#include <iomanip>
#include <map>
#include <stdexcept>

Json link_modules(std::istream& in) {
    struct Instruction { std::string mode, target; int opcode, value; };
    struct Module { std::string name; int base; std::vector<std::pair<std::string,int>> definitions; std::vector<Instruction> code; };
    struct Symbol { int address; std::string module; bool used=false; };
    int limit,count,base=0;
    if (!(in>>limit>>count) || limit<1 || limit>65536 || count<1 || count>32) throw std::invalid_argument("Invalid linker header.");
    std::vector<Module> modules;
    std::map<std::string,int> module_indices;
    for (int i=0;i<count;++i) {
        Module m; int definitions,size;
        if (!(in>>std::quoted(m.name)>>definitions>>size) || definitions<0 || definitions>128 || size<1 || size>1024)
            throw std::invalid_argument("Invalid object module.");
        if (module_indices.count(m.name)) throw std::invalid_argument("Module names must be unique.");
        m.base=base; module_indices[m.name]=i; base+=size;
        if (base>limit) throw std::invalid_argument("Object modules exceed the address space.");
        for (int j=0;j<definitions;++j) {
            std::string symbol;
            int offset;
            if (!(in >> std::quoted(symbol) >> offset)) throw std::invalid_argument("Invalid symbol definition.");
            m.definitions.emplace_back(symbol,offset);
        }
        for (int j=0;j<size;++j) {
            Instruction code;
            if (!(in >> code.mode >> code.opcode >> code.value >> std::quoted(code.target)) || code.opcode<0 || code.opcode>99)
                throw std::invalid_argument("Invalid object instruction.");
            m.code.push_back(code);
        }
        modules.push_back(m);
    }
    Json events=Json::array(), diagnostics=Json::array(), memory=Json::array();
    std::map<std::string,Symbol> symbols;
    int errors=0,warnings=0,index=0;
    auto diagnostic=[&](const std::string& level,const std::string& code,const std::string& message,const std::string& module,int address) {
        if(level=="error") ++errors;else ++warnings;
        Json d=Json::object({{"level",level},{"code",code},{"message",message},{"module",module},{"address",address}});
        diagnostics.push(d);return d;
    };
    auto symbol_rows=[&]() {
        Json rows=Json::array();
        for(const auto& [name,symbol]:symbols) rows.push(Json::object({{"name",name},{"address",symbol.address},{"module",symbol.module},{"used",symbol.used}}));
        return rows;
    };
    for(const auto& m:modules) {
        Json notes=Json::array();
        for(const auto& [name,offset]:m.definitions) {
            if(symbols.count(name)) {
                notes.push(diagnostic("error","duplicate-symbol","Keep the first definition of "+name+".",m.name,m.base));continue;
            }
            int relative=offset;
            if(offset<0 || offset>=static_cast<int>(m.code.size())) {
                notes.push(diagnostic("error","definition-range","Definition "+name+" is outside its module; use offset 0.",m.name,m.base));relative=0;
            }
            symbols[name]={m.base+relative,m.name,false};
        }
        events.push(Json::object({{"index",index++},{"pass",1},{"module_name",m.name},{"base",m.base},
            {"size",int(m.code.size())},{"outcome","symbols"},{"symbols",symbol_rows()},{"diagnostics",notes}}));
    }
    for(const auto& m:modules) {
        for(int offset=0;offset<static_cast<int>(m.code.size());++offset) {
            const auto& code=m.code[offset];
            int resolved=code.value;
            Json notes=Json::array();
            auto error=[&](const std::string& kind,const std::string& message) {notes.push(diagnostic("error",kind,message,m.name,m.base+offset));};
            if(code.mode=="I") {}
            else if(code.mode=="A") {
                if(resolved<0 || resolved>=limit) {error("absolute-range","Absolute address is outside memory; use 0.");resolved=0;}
            } else if(code.mode=="R") {
                if(resolved<0 || resolved>=static_cast<int>(m.code.size())) {error("relative-range","Relative address is outside this module; use its base.");resolved=0;}
                resolved+=m.base;
            } else if(code.mode=="E") {
                const auto found=symbols.find(code.target);
                if(found==symbols.end()) {error("undefined-symbol","Symbol "+code.target+" is undefined; use 0.");resolved=0;}
                else {
                    found->second.used=true;
                    const long long target=static_cast<long long>(found->second.address)+code.value;
                    if(target<0 || target>=limit) {error("external-range","Symbol plus addend is outside memory; use 0.");resolved=0;}
                    else resolved=int(target);
                }
            } else if(code.mode=="M") {
                const auto found=module_indices.find(code.target);
                if(found==module_indices.end()) {error("undefined-module","Module "+code.target+" is undefined; use 0.");resolved=0;}
                else {
                    const auto& target=modules[found->second];
                    if(resolved<0 || resolved>=static_cast<int>(target.code.size())) {error("module-range","Offset is outside the target module; use its base.");resolved=0;}
                    resolved+=target.base;
                }
            } else throw std::invalid_argument("Addressing mode must be I, A, R, E, or M.");
            Json row=Json::object({{"address",m.base+offset},{"opcode",code.opcode},{"operand",resolved},{"module_name",m.name}});
            memory.push(row);
            events.push(Json::object({{"index",index++},{"pass",2},{"module_name",m.name},{"address",m.base+offset},
                {"mode",code.mode},{"target",code.target},{"original",code.value},{"resolved",resolved},
                {"opcode",code.opcode},{"outcome","relocate"},{"diagnostics",notes}}));
        }
    }
    for(const auto& [name,symbol]:symbols) if(!symbol.used)
        diagnostic("warning","unused-symbol","Symbol "+name+" is defined but never referenced.",symbol.module,symbol.address);
    return Json::object({{"module","linker"},{"events",events},{"symbols",symbol_rows()},{"memory",memory},
        {"diagnostics",diagnostics},{"summary",Json::object({{"modules",count},{"instructions",base},{"symbols",int(symbols.size())},{"errors",errors},{"warnings",warnings}})}});
}
