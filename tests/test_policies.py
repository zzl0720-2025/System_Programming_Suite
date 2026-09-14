import copy
import unittest

from test_memory import experiment
import suite


class PolicyTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        suite.build()

    def test_nru_prefers_clean_within_the_same_reference_class(self):
        config = {**experiment([1, 2, 3], 2, "nru"), "writes": [0], "reset_interval": 10}
        result = suite.run(config)
        self.assertEqual(result["events"][-1]["victim"], 2)
        self.assertEqual(result["summary"]["writebacks"], 0)

    def test_nru_prefers_unreferenced_dirty_over_referenced_clean(self):
        config = {**experiment([1, 2, 2, 3], 2, "nru"), "writes": [0], "reset_interval": 2}
        result = suite.run(config)
        self.assertEqual(result["events"][2]["cleared"], [0, 1])
        self.assertEqual(result["events"][-1]["victim"], 1)
        self.assertEqual(result["summary"]["writebacks"], 1)

    def test_aging_samples_before_the_next_access(self):
        result = suite.run({**experiment([1, 2, 1, 3], 2, "aging"), "reset_interval": 1})
        self.assertEqual(result["events"][1]["frames"][0]["age"], 0x80000000)
        self.assertEqual(result["events"][2]["frames"][0]["age"], 0x40000000)
        self.assertEqual(result["events"][-1]["frames"][0]["age"], 0xA0000000)
        self.assertEqual(result["events"][-1]["victim"], 2)

    def test_aging_ties_follow_the_hand(self):
        result = suite.run({**experiment([1, 2, 3, 4], 2, "aging"), "reset_interval": 20})
        self.assertEqual([e["victim"] for e in result["events"]], [-1, -1, 1, 2])

    def test_working_set_window_boundary_and_fallback(self):
        config = experiment([1, 2, 3, 4, 2, 5], 3, "working-set")
        short = suite.run({**config, "window": 1})
        boundary = suite.run({**config, "window": 2})
        self.assertEqual(short["events"][-1]["victim"], 3)
        self.assertEqual(short["events"][-1]["cleared"], [1])
        self.assertEqual(boundary["events"][-1]["victim"], 3)
        self.assertEqual(boundary["events"][-1]["cleared"], [1, 0])
        self.assertEqual(boundary["events"][3]["victim"], 1)

    def test_random_known_seed_and_draw_schedule(self):
        config = {**experiment([1, 2, 3, 1, 2, 4], 3, "random"), "seed": 1}
        result = suite.run(config)
        # The first MT19937(1) output is 1791095845; modulo 3 selects slot 1.
        self.assertEqual(result["events"][-1]["slot"], 1)
        self.assertEqual(result["events"][-1]["victim"], 2)
        self.assertEqual(result, suite.run(config))
        other = suite.run({**config, "seed": 0})
        self.assertEqual(other["events"][-1]["slot"], 2)

    def test_write_hit_marks_dirty_and_eviction_clears_it(self):
        for policy in suite.POLICIES:
            with self.subTest(policy=policy):
                result = suite.run({**experiment([1, 1, 2, 1], 1, policy), "writes": [1]})
                self.assertTrue(result["events"][1]["hit"])
                self.assertTrue(result["events"][1]["frames"][0]["dirty"])
                self.assertTrue(result["events"][2]["writeback"])
                self.assertFalse(result["events"][3]["frames"][0]["dirty"])
                self.assertEqual(result["summary"]["writebacks"], 1)

    def test_dirty_residents_are_not_flushed_at_end(self):
        result = suite.run({**experiment([1, 2]), "writes": [0, 1]})
        self.assertEqual(result["summary"]["writebacks"], 0)
        self.assertTrue(all(f["dirty"] for f in result["events"][-1]["frames"][:2]))

    def test_new_parameters_are_validated(self):
        base = experiment([1, 2])
        bad = [{"seed": -1}, {"seed": 2**32}, {"seed": True}, {"seed": "1"},
               {"writes": [True]}, {"writes": [2]}, {"writes": [0, 0]},
               {"writes": "0"}, {"reset_interval": 0}, {"window": 4097},
               {"alogrithm": "clock"}]
        for override in bad:
            with self.subTest(override=override), self.assertRaises(ValueError):
                suite.validate({**base, **override})

    def test_compare_does_not_mutate_the_experiment(self):
        config = {**experiment([1, 2, 3], 2), "writes": [0]}
        original = copy.deepcopy(config)
        rows = suite.compare(config, frame_counts=[1, 2])
        self.assertEqual(len(rows), 12)
        self.assertEqual(config, original)
        for row in rows:
            result = suite.run({**config, "frames": row["frames"], "algorithm": row["algorithm"]})
            self.assertEqual(row["faults"], result["summary"]["faults"])
            self.assertEqual(row["writebacks"], result["summary"]["writebacks"])

    def test_expert_workload_limit(self):
        result = suite.run(experiment([i % 65 for i in range(4096)], 64, "clock"))
        self.assertEqual(len(result["events"]), 4096)
        self.assertEqual(len(result["events"][-1]["frames"]), 64)


if __name__ == "__main__":
    unittest.main()
