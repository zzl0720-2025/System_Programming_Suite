import json
from pathlib import Path
import random
import subprocess
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import suite


def experiment(references, frames=3, algorithm="fifo"):
    return {"schema_version": 1, "module": "memory", "algorithm": algorithm,
            "frames": frames, "references": references}


class MemoryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        suite.build()

    def test_hits_do_not_change_fifo_arrival_order(self):
        result = suite.run(experiment([1, 2, 3, 1, 4]))
        self.assertEqual(result["summary"], {"accesses": 5, "faults": 4, "hits": 1, "writebacks": 0})
        self.assertEqual(result["events"][-1]["victim"], 1)
        self.assertEqual([frame["page"] for frame in result["events"][-1]["frames"]], [4, 2, 3])

    def test_clock_second_chance_preserves_recent_page(self):
        references = [1, 2, 3, 1, 4, 2, 5]
        clock = suite.run(experiment(references, algorithm="clock"))
        fifo = suite.run(experiment(references))
        self.assertEqual(clock["events"][4]["cleared"], [0, 1, 2])
        self.assertEqual(clock["events"][-1]["cleared"], [1])
        self.assertEqual(clock["events"][-1]["victim"], 3)
        self.assertEqual(fifo["events"][-1]["victim"], 2)

    def test_belady_counterexample(self):
        references = [1, 2, 3, 4, 1, 2, 5, 1, 2, 3, 4, 5]
        self.assertEqual(suite.run(experiment(references, 3))["summary"]["faults"], 9)
        self.assertEqual(suite.run(experiment(references, 4))["summary"]["faults"], 10)

    def test_single_frame_including_page_zero(self):
        for algorithm in suite.POLICIES:
            result = suite.run(experiment([0, 0, 999, 999, 0], 1, algorithm))
            self.assertEqual(result["summary"]["faults"], 3)
            self.assertEqual([event["victim"] for event in result["events"]], [-1, -1, 0, -1, 999])

    def test_no_eviction_when_all_distinct_pages_fit(self):
        for algorithm in suite.POLICIES:
            result = suite.run(experiment([1, 2, 3, 1, 2, 3], 8, algorithm))
            self.assertEqual(result["summary"]["faults"], 3)
            self.assertTrue(all(event["victim"] == -1 for event in result["events"]))

    def test_fifo_matches_independent_queue_model(self):
        rng = random.Random(417)
        for capacity in (1, 2, 3, 8):
            references = [rng.randrange(12) for _ in range(128)]
            queue = []
            faults = 0
            for page in references:
                if page not in queue:
                    faults += 1
                    if len(queue) == capacity:
                        queue.pop(0)
                    queue.append(page)
            result = suite.run(experiment(references, capacity))
            self.assertEqual(result["summary"]["faults"], faults)

    def test_trace_invariants_and_repeatability(self):
        references = [random.Random(72 + i).randrange(10) for i in range(128)]
        for algorithm in suite.POLICIES:
            config = experiment(references, 3, algorithm)
            result = suite.run(config)
            self.assertEqual(result, suite.run(config))
            previous_faults = 0
            previous_pages = set()
            for event in result["events"]:
                pages = [frame["page"] for frame in event["frames"] if frame["page"] >= 0]
                self.assertEqual(len(pages), len(set(pages)))
                self.assertIn(event["page"], pages)
                self.assertEqual(event["hit"], event["page"] in previous_pages)
                self.assertEqual(event["faults"], previous_faults + (not event["hit"]))
                if event["victim"] >= 0:
                    self.assertIn(event["victim"], previous_pages)
                    self.assertNotIn(event["victim"], pages)
                self.assertTrue(0 <= event["hand"] < 3)
                previous_faults = event["faults"]
                previous_pages = set(pages)

    def test_invalid_configurations_are_rejected(self):
        base = experiment([1])
        bad = [None, [], {}, {**base, "frames": True}, {**base, "frames": 0},
               {**base, "frames": 65}, {**base, "frames": 2.5},
               {**base, "references": []}, {**base, "references": [False]},
               {**base, "references": [-1]}, {**base, "references": [1000]},
               {**base, "references": [1] * 4097}, {**base, "algorithm": "unknown"},
               {**base, "module": "cpu"}, {**base, "schema_version": True}]
        for config in bad:
            with self.subTest(config=config), self.assertRaises(ValueError):
                suite.validate(config)

    def test_engine_rejects_invalid_direct_arguments(self):
        for arguments in (["fifo", "0", "1"], ["fifo", "3", "1x"],
                          ["clock", "2", "-1"], ["unknown", "2", "1"]):
            result = subprocess.run([str(suite.BINARY), *arguments], capture_output=True, text=True)
            self.assertEqual(result.returncode, 2)
            self.assertEqual(result.stdout, "")
            self.assertTrue(result.stderr.strip())

    def test_cli_and_library_return_the_same_trace(self):
        path = suite.ROOT / "examples" / "first-pages.json"
        output = subprocess.check_output([sys.executable, str(suite.ROOT / "suite.py"),
                                          "run", str(path)], text=True)
        self.assertEqual(json.loads(output), suite.run(json.loads(path.read_text())))


if __name__ == "__main__":
    unittest.main()
