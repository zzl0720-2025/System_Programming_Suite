import copy
import io
import json
from pathlib import Path
import random
import subprocess
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import engine
import module_api
from experiment_session import ExperimentSession


def experiment(module, **values):
    return {"schema_version": 1, "module": module, **values}


def example(module):
    return engine.load_config(engine.ROOT / "examples" / f"{module}.json")


class SchedulingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        module_api.build_native()

    def test_six_cpu_policy_traces(self):
        jobs = [{"arrival": 0, "priority": 0, "bursts": [3]},
                {"arrival": 1, "priority": 1, "bursts": [2]},
                {"arrival": 1, "priority": 3, "bursts": [1]}]
        expected = {"fcfs": [0,0,0,1,1,2], "lcfs": [0,0,0,2,1,1],
                    "srtf": [0,2,1,1,0,0], "rr": [0,0,1,1,2,0],
                    "prio": [0,0,2,1,1,0], "preprio": [0,2,1,1,0,0]}
        for policy, timeline in expected.items():
            with self.subTest(policy=policy):
                result = engine.run(experiment("cpu", algorithm=policy, quantum=2, processes=jobs))
                self.assertEqual([e["running"] for e in result["events"]], timeline)

    def test_cpu_io_idle_and_response(self):
        r = engine.run(experiment("cpu", processes=[{"arrival": 2, "bursts": [1,3,2]}]))
        self.assertEqual([e["running"] for e in r["events"]], [-1,-1,0,-1,-1,-1,0,0])
        self.assertEqual(r["processes"], [{"id":0,"finish":8,"response":0,"turnaround":6,"waiting":0}])
        self.assertAlmostEqual(r["summary"]["utilization"], 3/8)

    def test_srtf_equal_remaining_does_not_preempt(self):
        r = engine.run(experiment("cpu", algorithm="srtf", processes=[
            {"arrival":0,"bursts":[3]}, {"arrival":1,"bursts":[2]}]))
        self.assertEqual([e["running"] for e in r["events"]], [0,0,0,1,1])

    def test_rr_requeue_precedes_same_time_arrival(self):
        r = engine.run(experiment("cpu", algorithm="rr", quantum=2, processes=[
            {"arrival":0,"bursts":[3]}, {"arrival":2,"bursts":[1]}]))
        self.assertEqual([e["running"] for e in r["events"]], [0,0,0,1])

    def test_priority_expired_queue_waits_for_active_work(self):
        r = engine.run(experiment("cpu", algorithm="preprio", quantum=1, processes=[
            {"arrival":0,"priority":0,"bursts":[3]}, {"arrival":0,"priority":2,"bursts":[4]}]))
        self.assertEqual([e["running"] for e in r["events"]], [1,1,0,1,1,0,0])

    def test_cpu_time_conservation_on_generated_workloads(self):
        rng = random.Random(17)
        for _ in range(12):
            jobs = [{"arrival":rng.randrange(5), "priority":rng.randrange(4),
                     "bursts":[rng.randrange(1,5) for _ in range(rng.choice([1,3,5]))]} for _ in range(4)]
            for policy in module_api.ALGORITHMS["cpu"]:
                r = engine.run(experiment("cpu", algorithm=policy, quantum=2, processes=jobs))
                for metrics, job in zip(r["processes"], jobs):
                    self.assertEqual(metrics["turnaround"], metrics["waiting"] + sum(job["bursts"]))
                    executed = sum(e["running"]==metrics["id"] for e in r["events"])
                    self.assertEqual(executed, sum(job["bursts"][::2]))
                    self.assertGreaterEqual(metrics["waiting"], metrics["response"])
                    first = next(e["time"] for e in r["events"] if e["running"]==metrics["id"])
                    self.assertEqual(metrics["response"], first-job["arrival"])

    def test_five_disk_orders_and_seek_costs(self):
        requests = [{"arrival":0,"track":t} for t in [10,90,55,30]]
        expected = {"fifo":([0,1,2,3],180), "sstf":([2,3,0,1],130),
                    "look":([2,1,3,0],120), "clook":([2,1,0,3],140), "flook":([2,1,3,0],120)}
        for policy, (order, distance) in expected.items():
            r = engine.run(experiment("disk", algorithm=policy, head=50, requests=requests))
            self.assertEqual([e["request"] for e in r["events"]], order)
            self.assertEqual(r["summary"]["movement"], distance)
            self.assertEqual(r["summary"]["finish_time"], distance)

    def test_flook_freezes_batch(self):
        requests=[{"arrival":0,"track":60},{"arrival":0,"track":90},{"arrival":1,"track":65}]
        look=engine.run(experiment("disk",algorithm="look",head=50,requests=requests))
        flook=engine.run(experiment("disk",algorithm="flook",head=50,requests=requests))
        self.assertEqual([e["request"] for e in look["events"]], [0,2,1])
        self.assertEqual([e["request"] for e in flook["events"]], [0,1,2])

    def test_disk_idle_zero_distance_and_ties(self):
        for policy in module_api.ALGORITHMS["disk"]:
            r=engine.run(experiment("disk",algorithm=policy,head=50,requests=[
                {"arrival":3,"track":50},{"arrival":3,"track":50},{"arrival":5,"track":55}]))
            self.assertEqual([e["request"] for e in r["events"]],[-1,0,1,-1,2])
            self.assertEqual(r["summary"]["movement"],5)
            self.assertEqual(r["summary"]["finish_time"],10)
            self.assertEqual(r["summary"]["average_wait"],0)


class LinkerTests(unittest.TestCase):
    def test_five_modes_forward_reference(self):
        r=engine.run(example("linker"))
        self.assertEqual([i["operand"] for i in r["memory"]],[42,3,4,4,20])
        self.assertEqual([e["pass"] for e in r["events"]],[1,1,2,2,2,2,2])
        self.assertEqual(r["summary"]["errors"],0)

    def test_reordering_modules_relocates_symbols(self):
        config=example("linker");config["modules"].reverse()
        r=engine.run(config)
        self.assertEqual([i["operand"] for i in r["memory"]],[1,20,42,0,1])

    def test_duplicate_and_out_of_bounds_definition(self):
        config=example("linker")
        config["modules"][0]["definitions"]={"add":99}
        r=engine.run(config)
        self.assertEqual(next(s["address"] for s in r["symbols"] if s["name"]=="add"),0)
        self.assertEqual(r["memory"][1]["operand"],0)
        self.assertEqual(r["summary"]["errors"],2)

    def test_errors_have_deterministic_fallbacks(self):
        config=example("linker")
        config["modules"][0]["code"][1]["target"]="missing"
        config["modules"][0]["code"][2]["value"]=99
        config["modules"][1]["code"][0]["value"]=99
        config["modules"][1]["code"][1]["value"]=999
        r=engine.run(config)
        self.assertEqual([i["operand"] for i in r["memory"]],[42,0,3,3,0])
        self.assertEqual(r["summary"]["errors"],4)
        self.assertTrue(all(d["message"] for d in r["diagnostics"]))


class VirtualMemoryTests(unittest.TestCase):
    def test_process_isolation_and_offset(self):
        config=example("vm");config["instructions"]=config["instructions"][:2]
        r=engine.run(config);e=r["events"][-1]
        self.assertEqual([f["pid"] for f in e["frames"]],[0,1])
        self.assertEqual([v["physical"] for v in r["events"]],[16,4112])
        self.assertEqual(r["summary"]["faults"],2)

    def test_swap_roundtrip_and_file_exit(self):
        r=engine.run(example("vm"))
        for key,value in {"swap_outs":1,"swap_ins":1,"file_outs":1,"protection_faults":1,"segmentation_faults":1,"exits":2}.items():
            self.assertEqual(r["summary"][key],value,key)
        self.assertTrue(all(f["pid"]==-1 for f in r["events"][-1]["frames"]))
        self.assertTrue(all(not p["alive"] and not p["pages"] for p in r["events"][-1]["page_tables"]))

    def test_protected_write_does_not_dirty_page(self):
        config=example("vm");config["instructions"]=[{"op":"write","pid":0,"address":12288}]*2
        r=engine.run(config)
        self.assertEqual(r["summary"]["protection_faults"],2)
        self.assertEqual(r["summary"]["faults"],1)
        self.assertTrue(all(not f["dirty"] for f in r["events"][-1]["frames"]))
        self.assertEqual(r["events"][-1]["outcome"],"protection-fault")

    def test_invalid_and_exited_accesses_do_not_allocate(self):
        config=example("vm");config["instructions"]=[{"op":"read","pid":0,"address":999999},{"op":"exit","pid":0},{"op":"read","pid":0,"address":0}]
        r=engine.run(config)
        self.assertEqual(r["summary"]["faults"],0)
        self.assertEqual(r["summary"]["segmentation_faults"],2)
        self.assertTrue(all(f["page"]==-1 for f in r["events"][-1]["frames"]))

    def test_fifo_tracks_age_after_exit_frees_a_hole(self):
        config=example("vm");config["frames"]=3
        config["instructions"]=[{"op":op,"pid":pid,"address":address} for op,pid,address in [
            ('read',0,0),('read',1,0),('read',0,4096),('exit',1,0),('read',0,8192),('read',0,12288)]]
        e=engine.run(config)["events"][-1]
        self.assertEqual([f["page"] for f in e["frames"]],[3,2,1])

    def test_all_policies_repeat_and_preserve_page_table_mapping(self):
        for policy in engine.POLICIES:
            config={**example("vm"),"algorithm":policy}
            r=engine.run(config);self.assertEqual(r,engine.run(config))
            for e in r["events"]:
                occupied=[(f["pid"],f["page"]) for f in e["frames"] if f["pid"]>=0]
                self.assertEqual(len(occupied),len(set(occupied)))
                for process in e["page_tables"]:
                    for page in process["pages"]:
                        if page["present"]:
                            f=e["frames"][page["frame"]]
                            self.assertEqual((f["pid"],f["page"]),(process["pid"],page["page"]))


class ModuleInterfaceTests(unittest.TestCase):
    def test_native_adapter_rejects_truncated_input(self):
        module_api.build_native()
        cases={"cpu":"rr 2 1\n0 1 1\n", "disk":"fifo 50 1\n", 
               "linker":'256 1\n"main" 1 1\n"missing"\n',
               "vm":"fifo 2 4096 1 4 4 1 1\n0 1\n0\n"}
        for module,payload in cases.items():
            result=subprocess.run([str(module_api.BINARY),module],input=payload,text=True,capture_output=True)
            self.assertEqual(result.returncode,2,result.stdout)
            self.assertTrue(result.stderr)

    def test_invalid_shapes_and_fields_are_rejected(self):
        invalid=[experiment('cpu',processes=[{'arrival':0,'bursts':[1,2]}]),
                 experiment('disk',requests=[{'arrival':0,'track':True}]),
                 {**example('vm'),'page_size':300},
                 {**example('cpu'),'qunatum':3},
                 {**example('compiler'),'verify':'true'},
                 {**example('linker'),'memory_limit':1}]
        overlap=example('vm');overlap['processes'][0]['areas'].append({'start':0,'end':1});invalid.append(overlap)
        for config in invalid:
            with self.assertRaises(ValueError):engine.run(config)

    def test_cli_library_and_trace_replay_agree(self):
        for module in ('cpu','disk','vm','linker','compiler'):
            with self.subTest(module=module):
                config=example(module)
                if module=='compiler':config['verify']=False
                with tempfile.TemporaryDirectory() as directory:
                    path=Path(directory)/'experiment.json';path.write_text(json.dumps(config))
                    output=subprocess.check_output([sys.executable,str(engine.ROOT/'suite.py'),'run',str(path)],text=True)
                    result=json.loads(output);self.assertEqual(result,engine.run(config))
                    trace=Path(directory)/'trace.json';trace.write_text(output)
                    self.assertEqual(engine.verify_trace(trace),result)
                    result['events'][0]['outcome']='tampered';trace.write_text(json.dumps(result))
                    with self.assertRaises(ValueError):engine.verify_trace(trace)

    def test_shell_navigation_and_failed_edits(self):
        for module in ('cpu','disk','vm','linker','compiler'):
            config=example(module)
            if module=='compiler':config['verify']=False
            output=io.StringIO();session=ExperimentSession(config,stdout=output)
            for command in ('step 2','back','goto 0','run','summary','trace 2'):
                session.onecmd(command)
            self.assertEqual(session.errors,0,output.getvalue())
            before=copy.deepcopy((session.config,session.result,session.cursor))
            session.onecmd('set nonexistent 1')
            self.assertEqual((session.config,session.result,session.cursor),before)
            self.assertEqual(session.errors,1)

    def test_compare_and_exports(self):
        from reports import format_result
        for module in ('cpu','disk','vm'):
            config=example(module);before=copy.deepcopy(config)
            rows=engine.compare(config)
            self.assertEqual(len(rows),len(module_api.ALGORITHMS[module]))
            self.assertEqual(config,before)
            self.assertIn('algorithm',format_result(rows,'csv',comparison=True))
        for module in ('cpu','disk','vm','linker'):
            result=engine.run(example(module))
            self.assertIn('Full-run summary',format_result(result,'table'))
            self.assertGreater(len(format_result(result,'csv').splitlines()),1)
        with self.assertRaises(ValueError):engine.compare(example('vm'),frame_counts=[])


if __name__=='__main__':
    unittest.main()
