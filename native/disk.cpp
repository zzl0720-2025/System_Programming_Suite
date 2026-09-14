#include "engines.hpp"
#include <algorithm>
#include <cstdlib>
#include <stdexcept>

Json simulate_disk(std::istream& in) {
    struct Request { int id, arrival, track; };
    std::string algorithm;
    int head, count;
    if (!(in >> algorithm >> head >> count) || head<0 || head>9999 || count<1 || count>128)
        throw std::invalid_argument("Invalid disk header.");
    const std::vector<std::string> policies={"fifo","sstf","look","clook","flook"};
    if (std::find(policies.begin(),policies.end(),algorithm)==policies.end()) throw std::invalid_argument("Unknown disk policy.");
    std::vector<Request> future, active, incoming;
    for (int id=0;id<count;++id) {
        int arrival, track;
        if (!(in>>arrival>>track) || arrival<0 || arrival>100000 || track<0 || track>9999) throw std::invalid_argument("Invalid disk request.");
        future.push_back({id,arrival,track});
    }
    std::stable_sort(future.begin(),future.end(),[](auto a,auto b){return a.arrival<b.arrival;});
    int next=0,time=0,direction=1,movement=0,waits=0,turns=0,max_wait=0,index=0;
    Json events=Json::array(), metrics=Json::array();
    while (next<count || !active.empty() || !incoming.empty()) {
        while (next<count && future[next].arrival<=time) {
            (algorithm=="flook"?incoming:active).push_back(future[next++]);
        }
        if (algorithm=="flook" && active.empty()) active.swap(incoming);
        if (active.empty()) {
            const int end=future[next].arrival;
            events.push(Json::object({{"index",index++},{"time",time},{"end",end},{"request",-1},
                                      {"from",head},{"to",head},{"distance",0},{"movement",movement},{"direction",direction},{"waiting",0},
                                      {"outcome","idle"},{"queue",Json::array()},{"incoming",Json::array()}}));
            time=end; continue;
        }
        int chosen=0;
        auto nearest=[&](bool directional) {
            int best=-1;
            for (int i=0;i<static_cast<int>(active.size());++i) {
                int delta=active[i].track-head;
                if (directional && delta*direction<0) continue;
                if (best<0 || std::abs(delta)<std::abs(active[best].track-head)) best=i;
            }
            return best;
        };
        if (algorithm=="sstf") chosen=nearest(false);
        else if (algorithm=="look" || algorithm=="flook") {
            chosen=nearest(true);
            if (chosen<0) {direction=-direction;chosen=nearest(true);}
        } else if (algorithm=="clook") {
            chosen=nearest(true);
            if (chosen<0) chosen=static_cast<int>(std::min_element(active.begin(),active.end(),[](auto a,auto b){return a.track<b.track;})-active.begin());
        }
        const auto request=active[chosen];
        active.erase(active.begin()+chosen);
        const int distance=std::abs(head-request.track), end=time+distance, wait=time-request.arrival;
        movement+=distance; waits+=wait; turns+=end-request.arrival; max_wait=std::max(max_wait,wait);
        Json queue=Json::array(), staged=Json::array();
        for (const auto& r:active) queue.push(r.id);
        for (const auto& r:incoming) staged.push(r.id);
        events.push(Json::object({{"index",index++},{"time",time},{"end",end},{"request",request.id},
            {"arrival",request.arrival},{"from",head},{"to",request.track},{"distance",distance},
            {"waiting",wait},{"movement",movement},{"direction",direction},{"outcome","service"},{"queue",queue},{"incoming",staged}}));
        metrics.push(Json::object({{"id",request.id},{"start",time},{"finish",end},{"waiting",wait},{"turnaround",end-request.arrival}}));
        head=request.track;time=end;
    }
    return Json::object({{"module","disk"},{"algorithm",algorithm},{"events",events},{"requests",metrics},
        {"summary",Json::object({{"finish_time",time},{"movement",movement},{"average_wait",double(waits)/count},
            {"average_turnaround",double(turns)/count},{"max_wait",max_wait},{"utilization",time?double(movement)/time:0.0}})}});
}
