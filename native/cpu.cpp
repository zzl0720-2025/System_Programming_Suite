#include "engines.hpp"
#include <algorithm>
#include <stdexcept>

namespace {
struct Process {
    int id, arrival, priority;
    std::vector<int> bursts;
    int burst = 0, left = 0, remaining = 0, dynamic = 0;
    int wake = 0, order = 0, slice = 0, wait = 0, first = -1, finish = -1;
    std::string state = "new";
    bool expired = false;
};

Json states(const std::vector<Process>& processes) {
    Json rows = Json::array();
    for (const auto& p : processes)
        rows.push(Json::object({{"id",p.id},{"state",p.state},{"remaining",p.remaining},
                               {"priority",p.dynamic},{"waiting",p.wait},{"finish",p.finish},
                               {"expired",p.expired}}));
    return rows;
}
}

Json simulate_cpu(std::istream& in) {
    std::string algorithm;
    int quantum, count;
    if (!(in >> algorithm >> quantum >> count) || count < 1 || count > 32 || quantum < 1)
        throw std::invalid_argument("Invalid CPU header.");
    const std::vector<std::string> policies = {"fcfs","lcfs","srtf","rr","prio","preprio"};
    if (std::find(policies.begin(), policies.end(), algorithm) == policies.end())
        throw std::invalid_argument("Unknown CPU policy.");
    std::vector<Process> processes;
    int total_cpu = 0;
    for (int id = 0; id < count; ++id) {
        int arrival, priority, n;
        if (!(in >> arrival >> priority >> n) || arrival < 0 || priority < 0 || priority > 31 || n < 1 || n > 31 || n % 2 == 0)
            throw std::invalid_argument("Invalid process.");
        Process p{};
        p.id=id; p.arrival=arrival; p.priority=priority; p.dynamic=priority;
        for (int j=0;j<n;++j) {
            int duration;
            if (!(in >> duration) || duration < 1 || duration > 1000) throw std::invalid_argument("Invalid burst.");
            p.bursts.push_back(duration);
            if (j % 2 == 0) p.remaining += duration;
        }
        total_cpu += p.remaining;
        p.left = p.bursts[0];
        processes.push_back(p);
    }
    const bool priorities = algorithm == "prio" || algorithm == "preprio";
    const bool sliced = priorities || algorithm == "rr";
    int order = 0, running = -1, done = 0, time = 0, switches = 0;
    Json events = Json::array();
    auto enqueue = [&](Process& p, bool decay) {
        p.state = "ready"; p.order = order++;
        if (priorities && decay && --p.dynamic < 0) { p.dynamic = p.priority; p.expired = true; }
    };
    auto choose = [&](bool allow_swap=true) {
        if (priorities && allow_swap) {
            bool active = false;
            for (auto& p : processes) if (p.state == "ready" && !p.expired) active = true;
            if (!active) for (auto& p : processes) if (p.state == "ready") p.expired = false;
        }
        int best=-1;
        for (auto& p : processes) {
            if (p.state != "ready" || (priorities && p.expired)) continue;
            if (best < 0) { best=p.id; continue; }
            const auto& b=processes[best];
            bool better = p.order < b.order;
            if (algorithm == "lcfs") better = p.order > b.order;
            else if (algorithm == "srtf") better = p.remaining < b.remaining || (p.remaining == b.remaining && p.order < b.order);
            else if (priorities) better = p.dynamic > b.dynamic || (p.dynamic == b.dynamic && p.order < b.order);
            if (better) best=p.id;
        }
        return best;
    };
    while (done < count) {
        if (time >= 20000) throw std::invalid_argument("CPU experiment exceeds 20000 time units.");
        Json arrivals=Json::array();
        for (auto& p : processes) {
            if ((p.state=="new" && p.arrival==time) || (p.state=="blocked" && p.wake==time)) {
                p.dynamic=p.priority; p.expired=false; enqueue(p,false); arrivals.push(p.id);
            }
        }
        std::string reason="continue";
        int preempted=-1;
        if (running >= 0 && (algorithm=="srtf" || algorithm=="preprio")) {
            int candidate=choose(false);
            if (candidate >= 0 && (algorithm=="srtf" ? processes[candidate].remaining < processes[running].remaining
                 : processes[candidate].dynamic > processes[running].dynamic)) {
                preempted=running; enqueue(processes[running],priorities); running=-1; reason="preempt";
            }
        }
        if (running < 0) {
            running=choose();
            if (running >= 0) {
                auto& p=processes[running]; p.state="running"; p.slice=quantum;
                if (p.first<0) p.first=time;
                ++switches;
                if (reason!="preempt") reason="dispatch";
            } else reason="idle";
        }
        Json ready=Json::array();
        for (auto& p : processes) if (p.state=="ready") { ++p.wait; ready.push(p.id); }
        const int executed=running;
        std::string outcome=reason;
        if (running >= 0) {
            auto& p=processes[running]; --p.remaining; --p.left; --p.slice;
            if (p.left==0) {
                if (p.burst+1 == static_cast<int>(p.bursts.size())) {
                    p.finish=time+1; p.state="done"; ++done; outcome="complete";
                } else {
                    p.wake=time+1+p.bursts[p.burst+1]; p.burst+=2; p.left=p.bursts[p.burst]; p.state="blocked"; outcome="block";
                }
                running=-1;
            } else if (sliced && p.slice==0) {
                enqueue(p,priorities); running=-1; outcome="quantum-expired";
            }
        }
        events.push(Json::object({{"index",time},{"time",time},{"end",time+1},{"running",executed},
            {"reason",reason},{"outcome",outcome},{"preempted",preempted},{"arrivals",arrivals},
            {"ready",ready},{"processes",states(processes)}}));
        ++time;
    }
    double waits=0, turns=0, responses=0;
    Json metrics=Json::array();
    for (const auto& p : processes) {
        waits+=p.wait; turns+=p.finish-p.arrival; responses+=p.first-p.arrival;
        metrics.push(Json::object({{"id",p.id},{"finish",p.finish},{"waiting",p.wait},
                                  {"turnaround",p.finish-p.arrival},{"response",p.first-p.arrival}}));
    }
    return Json::object({{"module","cpu"},{"algorithm",algorithm},{"events",events},{"processes",metrics},
        {"summary",Json::object({{"finish_time",time},{"cpu_time",total_cpu},{"utilization",double(total_cpu)/time},
          {"average_wait",waits/count},{"average_turnaround",turns/count},{"average_response",responses/count},{"dispatches",switches}})}});
}
