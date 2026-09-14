import copy
import csv
import io
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from test_memory import experiment
import suite
from engine import load_config, verify_trace
from session import MemorySession


class SessionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        suite.build()

    def session(self):
        return MemorySession(experiment([1, 2, 3, 1, 4]), stdin=io.StringIO(), stdout=io.StringIO())

    def test_navigation_and_empty_lines(self):
        session = self.session()
        session.onecmd("step 4")
        self.assertEqual(session.cursor, 4)
        self.assertEqual(session.result["events"][3]["faults"], 3)
        session.onecmd("")
        self.assertEqual(session.cursor, 4)
        session.onecmd("back 2")
        self.assertEqual(session.cursor, 2)
        session.onecmd("goto 0")
        self.assertEqual(session.cursor, 0)
        session.onecmd("run")
        self.assertEqual(session.cursor, 5)
        session.onecmd("step")
        self.assertEqual(session.cursor, 5)

    def test_failed_edits_and_navigation_preserve_state(self):
        session = self.session()
        session.onecmd("step 2")
        before = (copy.deepcopy(session.config), session.result, session.cursor)
        for command in ("set frames 0", "set window -1", "refs w1000", "goto 999",
                        "refs 1 two", "set policy bogus", 'load "unterminated', "step -1"):
            session.onecmd(command)
            self.assertEqual((session.config, session.result, session.cursor), before)
        self.assertEqual(session.errors, 8)

    def test_compare_and_sweep_preserve_cursor_and_config(self):
        session = self.session()
        session.onecmd("step 2")
        before = (copy.deepcopy(session.config), session.result, session.cursor)
        session.onecmd("compare fifo nru aging")
        session.onecmd("sweep 2 3 4")
        self.assertEqual((session.config, session.result, session.cursor), before)
        self.assertEqual(session.errors, 0)

    def test_read_write_input_and_configuration_reset(self):
        session = self.session()
        session.onecmd("run")
        session.onecmd("refs 1 w2 r3 W2")
        self.assertEqual(session.config["references"], [1, 2, 3, 2])
        self.assertEqual(session.config["writes"], [1, 3])
        self.assertEqual(session.cursor, 0)
        session.onecmd("set policy nru")
        self.assertEqual(session.config["algorithm"], "nru")

    def test_save_load_replay_and_overwrite_protection(self):
        session = self.session()
        with tempfile.TemporaryDirectory() as directory:
            config_path = Path(directory) / "my experiment.json"
            trace_path = Path(directory) / "trace.json"
            session.onecmd(f'save "{config_path}"')
            self.assertEqual(load_config(config_path), session.config)
            session.onecmd(f'export "{trace_path}"')
            self.assertEqual(verify_trace(trace_path), session.result)
            old = config_path.read_bytes()
            session.onecmd("set frames 1")
            session.onecmd(f'save "{config_path}"')
            self.assertEqual(config_path.read_bytes(), old)
            session.onecmd(f'load "{config_path}"')
            self.assertEqual(session.config["frames"], 3)
            session.onecmd(f'replay "{trace_path}"')
            self.assertEqual(session.cursor, 0)
            broken = json.loads(trace_path.read_text())
            broken["events"][0]["faults"] = 999
            trace_path.write_text(json.dumps(broken))
            with self.assertRaises(ValueError):
                verify_trace(trace_path)

    def test_piped_shell_session_and_error_exit(self):
        command = [sys.executable, str(suite.ROOT / "suite.py"), "shell"]
        result = subprocess.run(command, input="set policy clock\nrefs 1 w2 3 1\nstep 3\nback\ncompare\nquit\n",
                                capture_output=True, text=True, timeout=15)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("clock | access 2/4", result.stdout)
        self.assertIn("working-set", result.stdout)
        bad = subprocess.run(command, input="set frames 0\nstate\nquit\n", capture_output=True, text=True)
        self.assertEqual(bad.returncode, 1)
        self.assertIn("Frame count must", bad.stdout)

    def test_batch_json_and_csv_outputs(self):
        base = [sys.executable, str(suite.ROOT / "suite.py")]
        result = subprocess.check_output(base + ["run", "--policy", "nru", "--frames", "2",
                                                 "--references", "w1 2 3"], text=True)
        self.assertEqual(json.loads(result)["writes"], [0])
        csv_text = subprocess.check_output(base + ["compare", "--algorithms", "fifo", "clock",
                                                    "--frame-counts", "2", "3", "--format", "csv"], text=True)
        rows = list(csv.DictReader(io.StringIO(csv_text)))
        self.assertEqual(len(rows), 4)
        self.assertEqual({row["algorithm"] for row in rows}, {"fifo", "clock"})


if __name__ == "__main__":
    unittest.main()
