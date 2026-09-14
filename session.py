"""Interactive memory experiments."""

import cmd
import json
import shlex
import subprocess

from engine import (CONFIG_KEYS, POLICIES, POLICY_NOTES, compare, load_config,
                    parse_references, run, validate, verify_trace, write_file)
from reports import comparison_table, state_table, summary, trace_table


class MemorySession(cmd.Cmd):
    intro = "Systems Suite / memory\nType help for commands. A blank line does nothing."
    prompt = "memory> "

    def __init__(self, config, stdin=None, stdout=None):
        super().__init__(stdin=stdin, stdout=stdout)
        self.use_rawinput = stdin is None
        self.errors = 0
        self.config = validate(config)
        self.result = run(self.config)
        self.cursor = 0

    def say(self, text):
        self.stdout.write(str(text) + "\n")

    def onecmd(self, line):
        try:
            return super().onecmd(line)
        except (ValueError, OSError, subprocess.SubprocessError) as error:
            self.errors += 1
            self.say(f"Error: {error}")
            return False

    def emptyline(self):
        pass

    def default(self, line):
        raise ValueError(f"Unknown command: {line.split()[0]}. Type help.")

    def args(self, text, low=0, high=0):
        values = shlex.split(text)
        if not low <= len(values) <= high:
            raise ValueError("Unexpected arguments. Type help followed by the command name.")
        return values

    def replace(self, config):
        config = validate(config)
        if config["module"] != "memory":
            raise ValueError("Open a new shell to change modules.")
        result = run(config)
        self.config, self.result, self.cursor = config, result, 0
        self.say("Experiment updated. Playback reset to access 0.")

    def do_policies(self, arg):
        """policies: list the six replacement policies and their rules."""
        self.args(arg)
        for policy in POLICIES:
            self.say(f"{policy:12} {POLICY_NOTES[policy]}")

    def do_config(self, arg):
        """config: print the active experiment as JSON."""
        self.args(arg)
        self.say(json.dumps(self.config, indent=2))

    def do_load(self, arg):
        """load PATH: load a JSON experiment. Quote paths containing spaces."""
        path, = self.args(arg, 1, 1)
        self.replace(load_config(path))

    def do_replay(self, arg):
        """replay PATH: verify a saved trace against the engine, then open it at access 0."""
        path, = self.args(arg, 1, 1)
        result = verify_trace(path)
        if result.get("module") != "memory":
            raise ValueError("The trace belongs to another module.")
        config = validate({key: result[key] for key in CONFIG_KEYS})
        self.config, self.result, self.cursor = config, result, 0
        self.say("Trace verified. Playback is at access 0.")

    def do_set(self, arg):
        """set FIELD VALUE: change policy, frames, seed, reset_interval, or window. Resets playback."""
        key, value = self.args(arg, 2, 2)
        key = "algorithm" if key == "policy" else key
        if key not in ("algorithm", "frames", "seed", "reset_interval", "window"):
            raise ValueError("Set policy, frames, seed, reset_interval, or window. Use refs for the workload.")
        self.replace({**self.config, key: value if key == "algorithm" else int(value)})

    def do_refs(self, arg):
        """refs 1 r2 w3 ...: replace the workload. Bare numbers are reads; w3 writes page 3."""
        references, writes = parse_references(arg)
        self.replace({**self.config, "references": references, "writes": writes})

    def do_step(self, arg):
        """step [N]: advance N accesses (default 1), showing events and current frames."""
        values = self.args(arg, 0, 1)
        count = int(values[0]) if values else 1
        if count < 1:
            raise ValueError("Step count must be positive.")
        end = min(self.cursor + count, len(self.result["events"]))
        if end == self.cursor:
            self.say("End of trace. Use back or reset to inspect earlier accesses.")
            return
        self.say(trace_table(self.result["events"][self.cursor:end]))
        self.cursor = end
        self.do_state("")

    def do_back(self, arg):
        """back [N]: rewind N accesses without changing the experiment."""
        values = self.args(arg, 0, 1)
        count = int(values[0]) if values else 1
        if count < 1:
            raise ValueError("Back count must be positive.")
        self.cursor = max(0, self.cursor - count)
        self.do_state("")

    def do_goto(self, arg):
        """goto N: show state after N accesses. Zero is the initial empty memory."""
        value, = self.args(arg, 1, 1)
        position = int(value)
        if not 0 <= position <= len(self.result["events"]):
            raise ValueError("Position is outside this trace.")
        self.cursor = position
        self.do_state("")

    def do_run(self, arg):
        """run: advance to the end and print the final state and summary."""
        self.args(arg)
        self.cursor = len(self.result["events"])
        self.do_state("")

    def do_reset(self, arg):
        """reset: rewind to access 0, preserving the configuration."""
        self.args(arg)
        self.cursor = 0
        self.do_state("")

    def do_state(self, arg):
        """state: show resident pages, reference/dirty bits, ages, and the scan hand."""
        self.args(arg)
        self.say(state_table(self.result, self.cursor))
        self.say(summary(self.result, self.cursor))

    def do_summary(self, arg):
        """summary: print metrics at the current playback position."""
        self.args(arg)
        self.say(summary(self.result, self.cursor))

    def do_trace(self, arg):
        """trace [N]: show the last N visited accesses (default 10)."""
        values = self.args(arg, 0, 1)
        count = int(values[0]) if values else 10
        if count < 1:
            raise ValueError("Trace count must be positive.")
        self.say(trace_table(self.result["events"][max(0, self.cursor-count):self.cursor]))

    def do_explain(self, arg):
        """explain: describe the current policy and the most recent event."""
        self.args(arg)
        self.say(POLICY_NOTES[self.config["algorithm"]])
        if not self.cursor:
            self.say("No access has run yet. Use step to begin.")
            return
        event = self.result["events"][self.cursor - 1]
        if event["hit"]:
            self.say(f"Page {event['page']} was resident. Its reference bit is now 1.")
        elif event["victim"] < 0:
            self.say(f"Page {event['page']} was missing; it used empty frame {event['slot'] + 1}.")
        else:
            self.say(f"Page {event['page']} replaced page {event['victim']} in frame {event['slot'] + 1}.")
        if event["cleared"]:
            self.say("Reference bits cleared in frames: " + ", ".join(str(i+1) for i in event["cleared"]))
        if event["writeback"]:
            self.say("The replaced page was dirty, so this access caused one simulated writeback.")
        if event["write"]:
            self.say("This is a write: the resident page is now dirty.")

    def do_compare(self, arg):
        """compare [POLICY ...]: compare full-run metrics; default is all six policies."""
        algorithms = self.args(arg, 0, 6) or POLICIES
        self.say(comparison_table(compare(self.config, algorithms)))
        self.say("Full-run results. The current experiment and playback position are unchanged.")

    def do_sweep(self, arg):
        """sweep N N ...: compare frame counts using the current policy."""
        frames = [int(value) for value in self.args(arg, 1, 64)]
        self.say(comparison_table(compare(self.config, [self.config["algorithm"]], frames)))
        self.say("Full-run results. The current experiment and playback position are unchanged.")

    def save(self, arg, data):
        values = self.args(arg, 1, 2)
        if len(values) == 2 and values[1] != "--force":
            raise ValueError("Use PATH followed by optional --force.")
        write_file(values[0], json.dumps(data, indent=2) + "\n", len(values) == 2)
        self.say(f"Saved {values[0]}")

    def do_save(self, arg):
        """save PATH [--force]: save the configuration as JSON. Existing files are preserved by default."""
        self.save(arg, self.config)

    def do_export(self, arg):
        """export PATH [--force]: export the complete trace, including unvisited events."""
        self.save(arg, self.result)

    def do_quit(self, arg):
        """quit: end this session."""
        self.args(arg)
        return True

    def do_EOF(self, arg):
        self.say("")
        return True

    def complete_set(self, text, line, begidx, endidx):
        choices = POLICIES if line.split()[1:2] in (["policy"], ["algorithm"]) else (
            "policy", "frames", "seed", "reset_interval", "window")
        return [word for word in choices if word.startswith(text)]

    def complete_compare(self, text, line, begidx, endidx):
        return [word for word in POLICIES if word.startswith(text)]
