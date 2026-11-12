import os
import tempfile
import unittest
from unittest import mock

import basicanalysis_api as api

MODELFACTORS = """"Number of processes";8;16
"Global efficiency";46.415927;39.057450
"-- Parallel efficiency";46.415927;41.121734
" -- Load balance";50.221662;50.184508
" -- Communication efficiency";92.422123;81.941093
"-- Computation scalability";100.000000;94.980065
"   -- CUDA Load Balance";50.295597;50.909263
"#"
"""

TALP = """"Metric",8 (4x1) [4D],16 (8x1) [8D]
"DEVICE Global efficiency",92.414193,77.763453
"-- Device Parallel efficiency",92.414193,81.408779
"   == Device Orchestration efficiency",92.493883,82.067731
"""

METADATA = ("[1] /t/a.prv, 8(4x2) processes, 8 tasks per node, 47.8MB, "
            "Detailed+MPI+CUDA mode\n")


class BasicAnalysisApiTests(unittest.TestCase):

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.run_dir = os.path.join(self.tmp.name, "results", "run1")
        os.makedirs(self.run_dir)
        for name, text in (("modelfactors.csv", MODELFACTORS),
                           ("talp_metrics.csv", TALP),
                           ("traces_metadata.txt", METADATA)):
            with open(os.path.join(self.run_dir, name), "w") as handle:
                handle.write(text)
        self.env = mock.patch.dict(os.environ, {"BA_ROOTS": self.tmp.name})
        self.env.start()

    def tearDown(self):
        self.env.stop()
        self.tmp.cleanup()

    def test_list_runs(self):
        runs = api.list_runs(self.tmp.name)
        self.assertEqual(len(runs), 1)
        self.assertEqual(runs[0]["traces"][0]["mode"], "Detailed+MPI+CUDA")
        self.assertEqual(runs[0]["tables"], ["application", "heterogeneous"])

    def test_get_metrics_keys_levels_and_status(self):
        data = api.get_metrics(self.run_dir, "application")
        metrics = {m["metric"]: m for m in
                   data["tables"]["application"]["metrics"]}
        self.assertNotIn("#", metrics)
        self.assertEqual(metrics["Global efficiency"]["key"], "global_eff")
        self.assertEqual(metrics["Global efficiency"]["level"], 0)
        self.assertEqual(metrics["Load balance"]["status"],
                         ["Critical", "Critical"])
        self.assertEqual(metrics["Communication efficiency"]["status"],
                         ["Good", "Attention"])
        self.assertEqual(metrics["CUDA Load Balance"]["key"],
                         "runtime_load_balance")

    def test_list_issues_order(self):
        issues = api.list_issues(self.run_dir)["issues"]
        self.assertEqual(issues[0]["metric"], "Global efficiency")
        names = [issue["metric"] for issue in issues]
        self.assertIn("Device Orchestration efficiency", names)
        self.assertNotIn("Computation scalability", names)
        levels = [issue["level"] for issue in issues]
        self.assertEqual(levels, sorted(levels))

    def test_explain_metric(self):
        info = api.explain_metric("Device Orchestration efficiency")
        self.assertEqual(info["key"], "dev_orches_eff")
        self.assertIn("max", info["formula"])
        self.assertTrue(info["next_steps"])
        self.assertIn("CUDA", api.explain_metric("CUDA Load balance")["name"])
        with self.assertRaises(ValueError):
            api.explain_metric("no such metric")

    def test_paths_outside_the_roots_are_refused(self):
        with self.assertRaises(ValueError):
            api.get_metrics("/etc")
        with self.assertRaises(ValueError):
            api.get_metrics(os.path.join(self.run_dir, "..", "..", ".."))

    def test_analyze_validates_its_arguments(self):
        trace = os.path.join(self.tmp.name, "a.prv")
        open(trace, "w").close()
        out = os.path.join(self.tmp.name, "out")
        with self.assertRaises(ValueError):
            api.analyze([trace], out, workload="1; rm -rf /")
        with self.assertRaises(ValueError):
            api.analyze([trace], out, scaling="fast")
        with self.assertRaises(ValueError):
            api.analyze(["/etc/passwd"], out)
        with self.assertRaises(ValueError):
            api.analyze([os.path.join(self.tmp.name, "results")], out)


if __name__ == "__main__":
    unittest.main()
