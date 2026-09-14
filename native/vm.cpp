#include "engines.hpp"
#include "../core/memory.hpp"
#include <map>
#include <set>
#include <stdexcept>

Json simulate_vm(std::istream& in) {
    struct Area {int start,end;bool read_only,file;};
    struct Process {int pid;bool alive=true;std::vector<Area> areas;std::set<int> touched,swapped;};
    std::string algorithm;
    int capacity,page_size,count,instruction_count;
    suite::MemoryOptions options;
    if(!(in>>algorithm>>capacity>>page_size>>options.seed>>options.reset_interval>>options.window>>count>>instruction_count)
       || count<1 || count>8 || instruction_count<1 || instruction_count>256 || page_size<256 || page_size>65536)
        throw std::invalid_argument("Invalid virtual memory header.");
    suite::MemoryMachine machine(algorithm,capacity,options);
    std::vector<Process> processes;
    std::map<int,int> pid_index;
    for(int i=0;i<count;++i) {
        int pid,n;
        if(!(in>>pid>>n) || n<1 || n>64 || pid_index.count(pid)) throw std::invalid_argument("Invalid process map.");
        Process p; p.pid=pid;pid_index[pid]=i;
        for(int j=0;j<n;++j) {int a,b,r,f;if(!(in>>a>>b>>r>>f) || a<0 || a>=b || b>64 || (r!=0 && r!=1) || (f!=0 && f!=1)) throw std::invalid_argument("Invalid virtual area.");p.areas.push_back({a,b,bool(r),bool(f)});}
        processes.push_back(p);
    }
    auto area_for=[&](int process,int page)->const Area* {
        for(const auto& area:processes[process].areas) if(page>=area.start && page<area.end) return &area;
        return nullptr;
    };
    int current=-1,faults=0,hits=0,segv=0,protected_writes=0,switches=0,swap_in=0,swap_out=0,file_in=0,file_out=0,zeros=0,exits=0;
    Json events=Json::array();
    for(int index=0;index<instruction_count;++index) {
        std::string operation;int pid,address;
        if(!(in>>operation>>pid>>address) || !pid_index.count(pid)) throw std::invalid_argument("Unknown process in memory instruction.");
        const int process=pid_index[pid];auto& p=processes[process];
        const int page=address/page_size,offset=address%page_size;
        int physical=-1;
        bool fault=false;
        Json actions=Json::array();
        std::string outcome=operation;
        if(!p.alive) {++segv;outcome="process-exited";actions.push("reject access to exited process");}
        else if(operation=="exit") {
            for(const auto frame:machine.frames()) if(frame.page>=0 && frame.page/64==process) {
                const auto* area=area_for(process,frame.page%64);
                if(frame.dirty && area->file) {++file_out;actions.push("file-out");}
                actions.push("unmap");machine.release(frame.page);
            }
            p.alive=false;p.swapped.clear();p.touched.clear();++exits;
            if(current==pid) current=-1;
        } else if(operation=="switch") {
            if(current!=pid) {current=pid;++switches;} actions.push("switch address space");
        } else if(operation=="read" || operation=="write") {
            if(current!=pid) {current=pid;++switches;actions.push("switch address space");}
            const auto* area=address>=0?area_for(process,page):nullptr;
            if(!area) {++segv;outcome="segmentation-fault";actions.push("reject unmapped virtual address");}
            else {
                const int key=process*64+page;
                const bool denied=operation=="write" && area->read_only;
                const auto result=machine.access(key,operation=="write" && !denied);
                p.touched.insert(page);fault=!result.hit;
                if(result.hit) ++hits;
                else {
                    ++faults;
                    if(result.victim>=0) {
                        actions.push("unmap");
                        int owner=result.victim/64,vpage=result.victim%64;
                        if(result.writeback) {
                            if(area_for(owner,vpage)->file) {++file_out;actions.push("file-out");}
                            else {++swap_out;processes[owner].swapped.insert(vpage);actions.push("swap-out");}
                        }
                    }
                    if(area->file) {++file_in;actions.push("file-in");}
                    else if(p.swapped.count(page)) {++swap_in;actions.push("swap-in");}
                    else {++zeros;actions.push("zero-fill");}
                    actions.push("map");
                }
                physical=result.slot*page_size+offset;
                outcome=denied?"protection-fault":result.hit?"hit":"page-fault";
                if(denied) {++protected_writes;actions.push("reject protected write");}
                else actions.push(operation);
            }
        } else throw std::invalid_argument("Unknown memory operation.");
        Json frames=Json::array(),tables=Json::array();
        const auto& resident=machine.frames();
        for(int slot=0;slot<static_cast<int>(resident.size());++slot) {
            const auto& f=resident[slot];
            frames.push(Json::object({{"slot",slot},{"pid",f.page<0?-1:processes[f.page/64].pid},
                {"page",f.page<0?-1:f.page%64},{"referenced",f.referenced},{"dirty",f.dirty},
                {"age",static_cast<long long>(f.age)},{"last_seen",f.last_seen}}));
        }
        for(int owner=0;owner<count;++owner) {
            Json pages=Json::array();
            for(int vpage:processes[owner].touched) {
                int slot=-1;
                for(int j=0;j<static_cast<int>(resident.size());++j) if(resident[j].page==owner*64+vpage) slot=j;
                const auto* area=area_for(owner,vpage);
                pages.push(Json::object({{"page",vpage},{"frame",slot},{"present",slot>=0},
                    {"referenced",slot>=0 && resident[slot].referenced},{"dirty",slot>=0 && resident[slot].dirty},
                    {"swapped",bool(processes[owner].swapped.count(vpage))},{"read_only",area->read_only},{"file_mapped",area->file}}));
            }
            tables.push(Json::object({{"pid",processes[owner].pid},{"alive",processes[owner].alive},{"pages",pages}}));
        }
        events.push(Json::object({{"index",index},{"pid",pid},{"operation",operation},{"address",address},
            {"page",page},{"offset",offset},{"physical",physical},{"outcome",outcome},{"fault",fault},
            {"actions",actions},{"frames",frames},{"page_tables",tables},{"current_pid",current},{"faults",faults}}));
    }
    return Json::object({{"module","vm"},{"algorithm",algorithm},{"events",events},{"summary",Json::object({
        {"instructions",instruction_count},{"faults",faults},{"hits",hits},{"context_switches",switches},
        {"segmentation_faults",segv},{"protection_faults",protected_writes},{"swap_ins",swap_in},{"swap_outs",swap_out},
        {"file_ins",file_in},{"file_outs",file_out},{"zero_fills",zeros},{"exits",exits}})}});
}
