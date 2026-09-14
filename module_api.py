"""Validated inputs for the scheduling, linking, compiler, and virtual-memory engines."""

import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile

from engine import ROOT, POLICIES, integer

BINARY=ROOT/"build"/"systems-engine"
ALGORITHMS={"cpu":("fcfs","lcfs","srtf","rr","prio","preprio"),
            "disk":("fifo","sstf","look","clook","flook"),"vm":POLICIES,
            "linker":(),"compiler":()}


def build_native():
    sources=sorted((ROOT/"native").glob("*.cpp"))+[ROOT/"core"/"memory.cpp"]
    dependencies=sources+list((ROOT/"native").glob("*.hpp"))+[ROOT/"core"/"memory.hpp"]
    if BINARY.exists() and BINARY.stat().st_mtime>=max(p.stat().st_mtime for p in dependencies):
        return
    compiler=shutil.which(os.environ.get("CXX","c++"))
    if not compiler:
        raise ValueError("A C++17 compiler is required.")
    BINARY.parent.mkdir(exist_ok=True)
    fd,temporary=tempfile.mkstemp(prefix="systems-",dir=BINARY.parent);os.close(fd)
    try:
        process=subprocess.run([compiler,"-std=c++17","-O2","-Wall","-Wextra","-pedantic",*map(str,sources),"-o",temporary],capture_output=True,text=True)
        if process.returncode:
            raise ValueError("Native build failed:\n"+process.stderr)
        os.replace(temporary,BINARY)
    finally:
        Path(temporary).unlink(missing_ok=True)


def fields(value, allowed, label):
    if not isinstance(value,dict):
        raise ValueError(f"{label} must be an object.")
    extra=value.keys()-set(allowed)
    if extra:
        raise ValueError(f"Unknown {label} fields: {', '.join(sorted(extra))}.")


def sequence(value,label,maximum):
    if not isinstance(value,list) or not 1<=len(value)<=maximum:
        raise ValueError(f"{label} must contain 1 to {maximum} items.")
    return value


def name(value,label):
    if not isinstance(value,str) or not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]{0,31}",value):
        raise ValueError(f"{label} must be an identifier of at most 32 characters.")
    return value


def boolean(value,label):
    if type(value) is not bool:
        raise ValueError(f"{label} must be true or false.")
    return value


def validate(config):
    if not isinstance(config,dict):
        raise ValueError("An experiment must be a JSON object.")
    integer(config.get("schema_version"),"schema_version",1,1)
    module=config.get("module")
    if not isinstance(module,str) or module not in ALGORITHMS:
        raise ValueError("Choose memory, vm, cpu, disk, linker, or compiler.")
    allowed={
        "cpu":("algorithm","quantum","processes"),"disk":("algorithm","head","requests"),
        "vm":("algorithm","frames","page_size","seed","reset_interval","window","processes","instructions"),
        "linker":("memory_limit","modules"),"compiler":("source","verify"),
    }[module]
    fields(config,(*allowed,"schema_version","module"),"experiment")
    result={"schema_version":1,"module":module}
    if ALGORITHMS[module]:
        algorithm=config.get("algorithm",ALGORITHMS[module][0])
        if algorithm not in ALGORITHMS[module]:
            raise ValueError(f"Choose a {module} policy: {', '.join(ALGORITHMS[module])}.")
        result["algorithm"]=algorithm
    if module=="cpu":
        result["quantum"]=integer(config.get("quantum",2),"Quantum",1,1000)
        result["processes"]=[]
        for p in sequence(config.get("processes"),"Processes",32):
            fields(p,("arrival","priority","bursts"),"process")
            bursts=sequence(p.get("bursts"),"Bursts",31)
            if len(bursts)%2==0:
                raise ValueError("Bursts must alternate CPU and I/O, beginning and ending with CPU.")
            result["processes"].append({"arrival":integer(p.get("arrival"),"Arrival",0,1000),
                "priority":integer(p.get("priority",1),"Priority",0,31),
                "bursts":[integer(v,"Burst",1,1000) for v in bursts]})
        if sum(sum(p["bursts"]) for p in result["processes"])+max(p["arrival"] for p in result["processes"])>10000:
            raise ValueError("Total burst durations plus the last arrival must not exceed 10000.")
    elif module=="disk":
        result["head"]=integer(config.get("head",0),"Initial head",0,9999)
        result["requests"]=[]
        for request in sequence(config.get("requests"),"Requests",128):
            fields(request,("arrival","track"),"request")
            result["requests"].append({"arrival":integer(request.get("arrival"),"Arrival",0,100000),
                                       "track":integer(request.get("track"),"Track",0,9999)})
    elif module=="linker":
        result["memory_limit"]=integer(config.get("memory_limit",256),"Address space",1,65536)
        result["modules"]=[];names=set()
        for item in sequence(config.get("modules"),"Modules",32):
            fields(item,("name","definitions","code"),"object module")
            identifier=name(item.get("name"),"Module name")
            if identifier in names: raise ValueError("Module names must be unique.")
            names.add(identifier)
            definitions=item.get("definitions",{})
            if not isinstance(definitions,dict) or len(definitions)>128: raise ValueError("Definitions must be an object with at most 128 symbols.")
            definitions={name(k,"Symbol"):integer(v,"Definition offset",-65536,65536) for k,v in definitions.items()}
            code=[]
            for instruction in sequence(item.get("code"),"Code",1024):
                fields(instruction,("mode","opcode","value","target"),"instruction")
                mode=instruction.get("mode")
                if mode not in ("I","A","R","E","M"): raise ValueError("Addressing mode must be I, A, R, E, or M.")
                target=name(instruction.get("target"),"Reference target") if mode in ("E","M") else ""
                if mode not in ("E","M") and instruction.get("target","")!="": raise ValueError("Only E and M instructions have a target.")
                code.append({"mode":mode,"opcode":integer(instruction.get("opcode",0),"Opcode",0,99),
                             "value":integer(instruction.get("value",0),"Operand",-(2**31),2**31-1),"target":target})
            result["modules"].append({"name":identifier,"definitions":definitions,"code":code})
        if sum(len(m["code"]) for m in result["modules"])>result["memory_limit"]: raise ValueError("Modules do not fit in the address space.")
    elif module=="vm":
        result.update({"frames":integer(config.get("frames",3),"Frame count",1,32),
            "page_size":integer(config.get("page_size",4096),"Page size",256,65536),
            "seed":integer(config.get("seed",1),"Seed",0,2**32-1),
            "reset_interval":integer(config.get("reset_interval",4),"Reset interval",1,4096),
            "window":integer(config.get("window",4),"Working-set window",1,4096)})
        if result["page_size"] & (result["page_size"]-1): raise ValueError("Page size must be a power of two.")
        result["processes"]=[];pids=set()
        for p in sequence(config.get("processes"),"Processes",8):
            fields(p,("pid","areas"),"process")
            pid=integer(p.get("pid"),"Process ID",0,999)
            if pid in pids: raise ValueError("Process IDs must be unique.")
            pids.add(pid);areas=[];covered=set()
            for area in sequence(p.get("areas"),"Areas",64):
                fields(area,("start","end","read_only","file_mapped"),"virtual area")
                a=integer(area.get("start"),"Area start",0,63);b=integer(area.get("end"),"Area end",1,64)
                if a>=b or covered.intersection(range(a,b)): raise ValueError("Virtual areas must be nonempty and must not overlap.")
                covered.update(range(a,b));areas.append({"start":a,"end":b,"read_only":boolean(area.get("read_only",False),"read_only"),"file_mapped":boolean(area.get("file_mapped",False),"file_mapped")})
            result["processes"].append({"pid":pid,"areas":areas})
        result["instructions"]=[]
        for instruction in sequence(config.get("instructions"),"Instructions",256):
            fields(instruction,("op","pid","address"),"memory instruction")
            op=instruction.get("op");pid=integer(instruction.get("pid"),"Process ID",0,999)
            if op not in ("switch","read","write","exit") or pid not in pids: raise ValueError("Each memory instruction needs a known process and operation.")
            address=integer(instruction.get("address",0),"Virtual address",0,2**31-1)
            if op in ("read","write") and "address" not in instruction: raise ValueError("Read and write instructions need an address.")
            if op in ("switch","exit") and address!=0: raise ValueError("Switch and exit instructions do not take an address.")
            result["instructions"].append({"op":op,"pid":pid,"address":address})
    else:
        source=config.get("source")
        if not isinstance(source,str) or not source.strip() or len(source.encode())>8192: raise ValueError("Source must contain 1 to 8192 bytes.")
        result.update({"source":source,"verify":boolean(config.get("verify",True),"verify")})
    return result


def native_input(config):
    module=config["module"];lines=[]
    if module=="cpu":
        lines.append(f"{config['algorithm']} {config['quantum']} {len(config['processes'])}")
        for p in config["processes"]: lines.append(f"{p['arrival']} {p['priority']} {len(p['bursts'])} "+" ".join(map(str,p["bursts"])))
    elif module=="disk":
        lines.append(f"{config['algorithm']} {config['head']} {len(config['requests'])}")
        lines += [f"{r['arrival']} {r['track']}" for r in config["requests"]]
    elif module=="linker":
        lines.append(f"{config['memory_limit']} {len(config['modules'])}")
        for m in config["modules"]:
            lines.append(f"{json.dumps(m['name'])} {len(m['definitions'])} {len(m['code'])}")
            lines += [f"{json.dumps(k)} {v}" for k,v in m["definitions"].items()]
            lines += [f"{c['mode']} {c['opcode']} {c['value']} {json.dumps(c['target'])}" for c in m["code"]]
    else:
        lines.append(f"{config['algorithm']} {config['frames']} {config['page_size']} {config['seed']} {config['reset_interval']} {config['window']} {len(config['processes'])} {len(config['instructions'])}")
        for p in config["processes"]:
            lines.append(f"{p['pid']} {len(p['areas'])}")
            lines += [f"{a['start']} {a['end']} {int(a['read_only'])} {int(a['file_mapped'])}" for a in p["areas"]]
        lines += [f"{i['op']} {i['pid']} {i['address']}" for i in config["instructions"]]
    return "\n".join(lines)+"\n"


def run(config):
    config=validate(config)
    if config["module"]=="compiler":
        import compiler_driver
        result=compiler_driver.run(config)
    else:
        build_native()
        process=subprocess.run([str(BINARY),config["module"]],input=native_input(config),capture_output=True,text=True,timeout=20)
        if process.returncode: raise ValueError(process.stderr.strip() or "Native simulation failed.")
        result=json.loads(process.stdout)
    result["schema_version"]=1;result["config"]=config
    return result


def compare(config,algorithms=None,frame_counts=None):
    config=validate(config);module=config["module"]
    if not ALGORITHMS[module]: raise ValueError(f"The {module} module has no scheduling policies to compare.")
    algorithms=ALGORITHMS[module] if algorithms is None else algorithms
    if not algorithms or any(a not in ALGORITHMS[module] for a in algorithms): raise ValueError("Unknown comparison policy.")
    if frame_counts is not None and module!="vm": raise ValueError("Frame sweeps are only available for memory experiments.")
    counts=frame_counts if frame_counts is not None else [config.get("frames")]
    if not counts or len(counts)>32: raise ValueError("Choose 1 to 32 frame counts.")
    rows=[]
    for count in counts:
        for algorithm in algorithms:
            trial={**config,"algorithm":algorithm}
            if count is not None:trial["frames"]=count
            result=run(trial)
            rows.append({"algorithm":algorithm,**({"frames":count} if count is not None else {}),**result["summary"]})
    return rows
