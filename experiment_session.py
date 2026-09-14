"""Interactive sessions for the other suite modules."""

import json
from pathlib import Path

from engine import compare, run, validate, verify_trace
from module_api import ALGORITHMS
from reports import comparison_table, module_rows, table
from session import MemorySession


class ExperimentSession(MemorySession):
    def __init__(self,config,stdin=None,stdout=None):
        super().__init__(config,stdin,stdout)
        self.prompt=f"{self.config['module']}> "
        self.intro=f"Systems Suite / {self.config['module']}\nType help for commands; set FIELD JSON changes a parameter."

    def replace(self,config):
        config=validate(config)
        if config["module"]!=self.config["module"]:
            raise ValueError("Open a new shell to change modules.")
        result=run(config)
        self.config,self.result,self.cursor=config,result,0
        self.say("Experiment updated. Playback reset to step 0.")

    def do_set(self,arg):
        """set FIELD VALUE: update a field. Use quoted JSON for process lists, requests, or instructions."""
        key,value=self.args(arg,2,2)
        if key in ("schema_version","module"): raise ValueError("Open a new session to change the module.")
        if key=="policy":key="algorithm"
        try:value=json.loads(value)
        except json.JSONDecodeError:pass
        self.replace({**self.config,key:value})

    def do_source(self,arg):
        """source PATH: load a source file in a compiler session."""
        if self.config["module"]!="compiler":raise ValueError("source is available in compiler sessions.")
        path,=self.args(arg,1,1)
        self.replace({**self.config,"source":Path(path).read_text()})

    def do_refs(self,arg):
        """refs: use set instructions for virtual memory, or set processes/requests for scheduling."""
        raise ValueError("Use set or load to change this module's workload.")

    def do_policies(self,arg):
        """policies: list policies implemented by the current module."""
        self.args(arg)
        self.say(", ".join(ALGORITHMS[self.config["module"]]) or "This module has no replacement or scheduling policies.")

    def do_state(self,arg):
        """state: show the current event and its state snapshot."""
        self.args(arg)
        self.say(f"{self.config['module']} | step {self.cursor}/{len(self.result['events'])}")
        if not self.cursor:
            self.say("Initial state. Use step to begin or config to inspect the workload.");return
        event=self.result["events"][self.cursor-1]
        rows=module_rows(self.result,[event]);self.say(table(list(rows[0]),[rows[0].values()]))
        if "processes" in event:
            self.say(table(("id","state","remaining","priority","waiting"),[[p[k] for k in ("id","state","remaining","priority","waiting")] for p in event["processes"]]))
        if "frames" in event:
            self.say(table(("frame","pid","page","R","D"),[[f["slot"],f["pid"],f["page"],int(f["referenced"]),int(f["dirty"])] for f in event["frames"]]))
            self.say("Page tables: "+json.dumps(event["page_tables"]))
        if "symbols" in event:self.say("Symbols: "+json.dumps(event["symbols"]))
        if "diagnostics" in event and event["diagnostics"]:self.say(json.dumps(event["diagnostics"],indent=2))
        if "assembly" in event:self.say(event["assembly"])
        if "ast" in event:self.say(json.dumps(event["ast"],indent=2))
        if "verification" in event:self.say(json.dumps(event["verification"],indent=2))

    def do_step(self,arg):
        """step [N]: advance N events and inspect the last event."""
        values=self.args(arg,0,1);count=int(values[0]) if values else 1
        if count<1:raise ValueError("Step count must be positive.")
        self.cursor=min(len(self.result["events"]),self.cursor+count);self.do_state("")

    def do_trace(self,arg):
        """trace [N]: print the last N visited events."""
        values=self.args(arg,0,1);count=int(values[0]) if values else 10
        if count<1:raise ValueError("Trace count must be positive.")
        rows=module_rows(self.result,self.result["events"][max(0,self.cursor-count):self.cursor])
        self.say(table(list(rows[0]),[r.values() for r in rows]) if rows else "No visited events.")

    def do_run(self,arg):
        """run: advance to the final state and show full-run metrics."""
        self.args(arg)
        self.cursor=len(self.result["events"])
        self.do_state("")
        self.do_summary("")

    def do_summary(self,arg):
        """summary: show full-run metrics, independent of the playback position."""
        self.args(arg);self.say("Full-run summary:\n"+json.dumps(self.result["summary"],indent=2))

    def do_explain(self,arg):
        """explain: inspect the current event's decisions and state."""
        self.do_state(arg)

    def do_compare(self,arg):
        """compare [POLICY ...]: compare full runs without changing the current experiment."""
        algorithms=self.args(arg,0,6) or None
        self.say(comparison_table(compare(self.config,algorithms)))

    def do_sweep(self,arg):
        """sweep N N ...: compare physical frame counts in virtual memory."""
        if self.config["module"]!="vm":raise ValueError("Frame sweeps are available in memory and vm sessions.")
        counts=[int(v) for v in self.args(arg,1,32)]
        self.say(comparison_table(compare(self.config,[self.config["algorithm"]],counts)))

    def do_replay(self,arg):
        """replay PATH: verify an exported trace and open it at step 0."""
        path,=self.args(arg,1,1);result=verify_trace(path)
        if result.get("module")!=self.config["module"]:raise ValueError("The trace belongs to another module.")
        self.config,self.result,self.cursor=result["config"],result,0
        self.say("Trace verified. Playback is at step 0.")

    def complete_compare(self,text,line,begidx,endidx):
        return [p for p in ALGORITHMS[self.config["module"]] if p.startswith(text)]

    def complete_set(self,text,line,begidx,endidx):
        choices=ALGORITHMS[self.config["module"]] if line.split()[1:2] in (["policy"],["algorithm"]) else self.config.keys()
        return [key for key in choices if key.startswith(text)]
